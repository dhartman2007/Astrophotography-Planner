from datetime import datetime
from zoneinfo import ZoneInfo
import json
import pandas as pd
import streamlit as st
from plan_pdf import build_plan_pdf
from imaging_guidance import guidance
from core import catalog, plan, track, records, save, image_urls, forecast, DATA, remember_api_key, remembered_api_key, forecast_us_units, planned_targets, set_planned
st.set_page_config(page_title='Darkwave Target Planner',page_icon='🔭',layout='wide')
st.title('🔭 Darkwave Target Planner')
st.caption('Messier • NGC • IC | Plan a night, explore the sky, track your images')
OBJECT_TYPE_LABELS = {
    "*": "Star",
    "**": "Double star",
    "*Ass": "Association of stars",
    "OCl": "Open cluster",
    "GCl": "Globular cluster",
    "Cl+N": "Star cluster with nebula",
    "G": "Galaxy",
    "GPair": "Galaxy pair",
    "GTrpl": "Galaxy triplet",
    "GGroup": "Group of galaxies",
    "PN": "Planetary nebula",
    "HII": "Ionized hydrogen region",
    "DrkN": "Dark nebula",
    "EmN": "Emission nebula",
    "Neb": "Nebula",
    "RfN": "Reflection nebula",
    "SNR": "Supernova remnant",
    "Nova": "Nova star",
    "NonEx": "Nonexistent catalog object",
    "Dup": "Duplicate catalog entry",
    "Other": "Other classification"
}

settings_file=DATA/'settings.json'
settings=json.loads(settings_file.read_text()) if settings_file.exists() else {}
with st.sidebar:
    st.header('Observing location')
    place=st.text_input('Location name',settings.get('place','Foley, Alabama'))
    lat=st.number_input('Latitude',-90.0,90.0,float(settings.get('lat',30.4066)),format='%.5f')
    lon=st.number_input('Longitude (west is negative)',-180.0,180.0,float(settings.get('lon',-87.6836)),format='%.5f')
    tz=st.text_input('Time zone',settings.get('tz','America/Chicago'))
    try: ZoneInfo(tz)
    except Exception: st.error('Use an IANA time zone such as America/Chicago.'); st.stop()
    if st.button('Save location'):
        settings_file.write_text(json.dumps(dict(place=place,lat=lat,lon=lon,tz=tz)))
        st.success('Location saved')
    day=st.date_input('Evening date',datetime.now(ZoneInfo(tz)).date())
    minimum=st.slider('Minimum target altitude',0,80,30)
    moon_sep=st.slider('Minimum Moon separation when Moon is up',0,180,30)
    south=st.slider('Southern obstruction height (azimuth 90–270°)',0,90,0)
    st.caption('Set 0° for an unobstructed southern sky. Times use the selected time zone, including DST.')
    fov_long=st.number_input('SeeStar frame long side (degrees)',0.1,10.0,2.8,step=0.1)
    fov_short=st.number_input('SeeStar frame short side (degrees)',0.1,10.0,1.575,step=0.1)
    st.caption('Approximate S50 Pro framing; adjust to your actual imaging mode. Suitability and integration are planning estimates.')
    api_key=st.text_input('Astrospheric API key',value=remembered_api_key(),type='password',help='Saved locally in this installation’s data folder and loaded on restart. Clear the field to forget it. Forecast requests use your API credits.')
    if api_key.strip() != remembered_api_key():
        try:
            remember_api_key(api_key)
        except OSError:
            st.error('Could not save the API key. Check that the data folder is writable.')
@st.cache_data(show_spinner='Loading OpenNGC catalogs…')
def load(): return catalog()
try: df=load()
except Exception as e:
    st.error('Catalog download failed. Connect to the internet or put OpenNGC NGC.csv and addendum.csv in the data folder.')
    st.caption(str(e));st.stop()
logs=records()
query=st.text_input('Search object, common name, or constellation',placeholder='M27, NGC6992, Andromeda…')
c1,c2,c3=st.columns(3)
collection=c1.selectbox('Catalog',['Messier','NGC','IC','All'])
types=c2.multiselect('Object types',sorted(df.Type.unique()),
                     format_func=lambda code: f'{code} — {OBJECT_TYPE_LABELS.get(code, code)}')
status=c3.selectbox('Imaging status',['All','Not imaged / needs reimage','Imaged','Needs reimage'])
filtered=df.copy()
if collection=='Messier': filtered=filtered[filtered.M!='']
elif collection in ['NGC','IC']: filtered=filtered[filtered.Name.str.startswith(collection)]
if query:
    compact=query.upper().replace(' ','')
    filtered=filtered[filtered.label.str.upper().str.replace(' ','').str.contains(compact,regex=False) | filtered.Const.str.contains(query,case=False,regex=False)]
if types: filtered=filtered[filtered.Type.isin(types)]
logmap=logs.set_index('object').to_dict('index') if len(logs) else {}
if status!='All':
    def matches(name):
        r=logmap.get(name,{})
        return (not r.get('imaged') or r.get('reimage')) if status=='Not imaged / needs reimage' else bool(r.get('imaged')) if status=='Imaged' else bool(r.get('reimage'))
    filtered=filtered[filtered.Name.map(matches)]
planned = planned_targets(day)
st.caption(f'{len(filtered):,} catalog entries • {place} • {day} • {tz}')
@st.cache_data(show_spinner='Calculating observing windows…',max_entries=8)
def calculate(rows,day,lat,lon,tz,minimum,moon_sep,south): return plan(rows,day,lat,lon,tz,minimum,moon_sep,south)
if filtered.empty: st.info('No matching objects.');st.stop()
try: results,dates,dark=calculate(filtered,day,lat,lon,tz,minimum,moon_sep,south)
except Exception as e: st.error(f'Calculation failed: {e}');st.stop()
results['Imaged']=results.Name.map(lambda n:bool(logmap.get(n,{}).get('imaged')))
results['Needs reimage']=results.Name.map(lambda n:bool(logmap.get(n,{}).get('reimage')))
results['Tonight’s plan'] = results.Name.isin(planned)
results=results.sort_values(['Hours','Peak °'],ascending=False)
only=st.checkbox('Only show targets with at least 2 usable hours')
shown=results[results.Hours>=2] if only else results
# Editing a plan checkbox persists immediately; Explore chooses the details below.
shown = shown.copy()
shown.insert(0, 'Explore', shown.Name.eq(st.session_state.get('explore_target')))
table_key = f"target_editor_{day.isoformat()}_{st.session_state.get('table_revision', 0)}"
def edit_target_table():
    changes = st.session_state.get(table_key, {}).get('edited_rows', {})
    for position, values in changes.items():
        position = int(position)
        if 0 <= position < len(shown):
            target = shown.iloc[position]['Name']
            if 'Tonight’s plan' in values:
                set_planned(day, target, bool(values['Tonight’s plan']))
            if values.get('Explore'):
                st.session_state['explore_target'] = target
    # A fresh editor prevents old edit deltas from being reapplied on later reruns.
    st.session_state['table_revision'] = st.session_state.get('table_revision', 0) + 1

st.data_editor(shown.drop(columns='Name'),hide_index=True,use_container_width=True,
               key=table_key,on_change=edit_target_table,
               disabled=[column for column in shown.columns if column not in ('Name', 'Explore', 'Tonight’s plan')],
               column_config={'Type': st.column_config.TextColumn('Type',help='Object classification code. Expand Legend below for the full meanings.'),
                              'Explore': st.column_config.CheckboxColumn('Explore',help='Check to show this target’s details below.'),
                              'Tonight’s plan': st.column_config.CheckboxColumn('Tonight’s plan',help='Add or remove this target for the selected date.')})
st.caption('Check Tonight’s plan to add or remove a target. Check Explore to display its details below.')

with st.expander('Legend — object types and observing columns'):
    st.markdown('**Object type codes**')
    st.table(pd.DataFrame(
        [(code, label) for code, label in OBJECT_TYPE_LABELS.items()],
        columns=['Code', 'Object type'],
    ))
    st.markdown('**Observing columns**')
    st.markdown("""
| Column | Meaning |
| --- | --- |
| Explore | Check to display this target's details below. |
| Hours | Total hours meeting the selected darkness, altitude, obstruction and Moon-separation limits. |
| Peak ° | Highest target altitude during astronomical darkness; 0° is the horizon and 90° is overhead. |
| Best window | Longest continuous usable imaging window, in the selected location's local time. |
| Moon-free h | Hours above the altitude/obstruction limits during darkness while the Moon is below the horizon. |
| Imaged | Your saved imaging-completion status; edit it in the target's imaging record. |
| Needs reimage | Your saved reminder to image the target again. |
| Tonight’s plan | Check to add the object to the selected date's plan and PDF. |
""")
    st.caption('Hours describe geometric visibility, not a weather forecast or guaranteed imaging time. Type codes follow OpenNGC.')
    st.link_button('OpenNGC catalog definitions', 'https://github.com/mattiaverga/OpenNGC/blob/master/NGC_guide.txt')


planned_results = pd.DataFrame()
if planned:
    planned_catalog = df[df.Name.isin(planned)]
    # Export the entire saved plan, even when a search hides some chosen targets.
    planned_results, plan_dates, plan_dark = calculate(planned_catalog,day,lat,lon,tz,minimum,moon_sep,south)
    planned_results = planned_results.sort_values('Best window')
export_plan, export_all = st.columns(2)
with export_plan:
    @st.cache_data(show_spinner=False,max_entries=4)
    def make_pdf(catalog,results,dates,dark,day,place,lat,lon,tz,minimum,moon_sep,south,weather,weather_note,fov_long,fov_short):
        return build_plan_pdf(catalog,results,dates,dark,day,place,lat,lon,tz,minimum,moon_sep,south,weather,weather_note,fov_long,fov_short)
    pdf_identity=(day.isoformat(),place,lat,lon,tz,minimum,moon_sep,south,tuple(sorted(planned)),fov_long,fov_short)
    if st.button('Generate tonight’s plan PDF',disabled=planned_results.empty):
        try:
            pdf_weather=None
            weather_note='Astrospheric forecast unavailable: no API key entered.'
            if api_key:
                try:
                    pdf_weather,metadata=forecast(api_key,lat,lon)
                    st.session_state['weather']=(lat,lon,pdf_weather,metadata)
                    weather_note=''
                except Exception as error:
                    weather_note=f'Astrospheric forecast unavailable: {error}'
                    st.warning(weather_note)
            with st.spinner('Building PDF and loading object images…'):
                pdf=make_pdf(planned_catalog,planned_results,plan_dates,plan_dark,day,place,lat,lon,tz,minimum,moon_sep,south,pdf_weather,weather_note,fov_long,fov_short)
            st.session_state['plan_pdf']=(pdf_identity,pdf)
        except Exception as e:
            st.session_state.pop('plan_pdf',None)
            st.error(f'PDF unavailable: {e}')
    saved_pdf=st.session_state.get('plan_pdf')
    if saved_pdf and saved_pdf[0]==pdf_identity:
        st.download_button('Download tonight’s plan PDF',saved_pdf[1],f'plan_{day.isoformat()}.pdf','application/pdf')
with export_all:
    st.download_button('Export all displayed targets',shown.to_csv(index=False),'targets.csv','text/csv')
st.caption('Geometry only: 5-minute samples, Sun below −18°, altitude and Moon limits applied. Weather is displayed separately; hours are not a clear-sky prediction. Moon-free means Moon below the geometric horizon.')
with st.expander(f'Tonight’s plan — {day.isoformat()} ({len(planned)} targets)', expanded=bool(planned)):
    if not planned_results.empty:
        st.dataframe(planned_results.drop(columns='Name'),hide_index=True,use_container_width=True)
    else:
        st.info('Check Tonight’s plan beside a target to include it in the plan export.')

if shown.empty: st.info('No targets meet these limits.');st.stop()
options = shown.Name.tolist()
if st.session_state.get('explore_target') not in options:
    st.session_state['explore_target'] = options[0]
name=st.selectbox('Explore target',options,key='explore_target',format_func=lambda n:df.loc[df.Name==n,'label'].iloc[0])
row=df[df.Name==name].iloc[0]
advice=guidance(row,dates,lat,lon,tz,minimum,moon_sep,south,fov_long,fov_short)
with st.expander('SeeStar suitability, Moon impact and imaging time',expanded=True):
    st.write(f'**SeeStar suitability: {advice["rating"]}**')
    st.write(advice['reason'])
    st.caption(advice['fov'])
    st.write('**Moon impact:** '+advice['moon'])
    st.write('**Filter:** '+advice['filter'])
    st.write('**Suggested integration:** '+advice['integration'])
    st.caption(advice['assumptions'])
plan_key = f'planned_{day.isoformat()}_{name}'
st.session_state[plan_key] = name in planned
def update_plan_checkbox():
    set_planned(day, name, st.session_state[plan_key])
    st.session_state['table_revision'] = st.session_state.get('table_revision', 0) + 1
st.checkbox('Add to tonight’s plan',value=name in planned,key=plan_key,on_change=update_plan_checkbox,
            help=f'Saved automatically for the observing night {day.isoformat()}. Uncheck to remove this target.')
a,b=st.columns([2,1])
with a:
    st.subheader(row.label)
    st.line_chart(track(row,dates,lat,lon,tz))
with b:
    st.write(f'**RA / Dec:** {row.RA} / {row.Dec}')
    st.write(f'**Constellation:** {row.Const} · **Type:** {row.Type} — {OBJECT_TYPE_LABELS.get(row.Type, row.Type)}')
    st.write(f"**Size:** {row.MajAx or '?'} × {row.MinAx or '?'} arcmin")
    st.write(f"**V magnitude:** {row['V-Mag'] or 'Unknown'}")
    old=logmap.get(name,{})
    with st.form('imaging_'+name):
        imaged=st.checkbox('Imaged',bool(old.get('imaged')))
        reimage=st.checkbox('Needs reimage',bool(old.get('reimage')))
        first=st.text_input('First image date (YYYY-MM-DD)',old.get('first_date',''))
        url=st.text_input('My image link',old.get('image_url',''))
        notes=st.text_area('Notes',old.get('notes',''))
        if st.form_submit_button('Save imaging record'):
            try:
                if first: datetime.strptime(first,'%Y-%m-%d')
                save(name,imaged,reimage,first,url,notes);st.rerun()
            except ValueError: st.error('Date must be YYYY-MM-DD, or blank.')
st.subheader('Reference gallery')
for col,(label,url) in zip(st.columns(3),image_urls(row)):
    with col:
        st.image(url,caption=label,use_container_width=True)
        st.link_button('Open survey image',url)
st.caption('Survey cutouts served by CDS HiPS2FITS: DSS2 (digitized photographic sky survey) and 2MASS (infrared). Three views, including two fields of view of DSS2; coverage and image availability vary. Infrared colors differ from visible-light imaging. These are reference images, not Seestar predictions.')
if api_key:
    if st.button('Load / refresh Astrospheric forecast'):
        try:
            weather,metadata=forecast(api_key,lat,lon)
            st.session_state['weather']=(lat,lon,weather,metadata)
        except Exception as e:
            st.session_state.pop('weather', None)
            st.error(f'Forecast unavailable: {e}')
    if 'weather' in st.session_state:
        wlat,wlon,weather,meta=st.session_state['weather']
        if (wlat,wlon)==(lat,lon) and not weather.empty:
            st.subheader('Astrospheric forecast')
            weather=forecast_us_units(weather)
            weather.index=pd.to_datetime(weather.index,utc=True).tz_convert(tz)
            st.dataframe(weather,use_container_width=True)
            st.caption('Temperature and dew point are °F; wind speed is mph. Cloud, transparency and seeing retain provider scales. Forecast times are local. Historical or distant selected dates may fall outside forecast coverage.')
            st.download_button('Export forecast',weather.to_csv(),'forecast.csv')
else: st.info('Enter your Astrospheric API key in the sidebar to load weather. Visibility calculations work without a key.')
st.download_button('Back up imaging log',logs.to_csv(index=False),'imaging_log.csv','text/csv')
