# Darkwave Target Planner

Python application with a local browser interface. Install Python 3.11 or 3.12 from python.org on Windows, extract this entire folder to a writable location, and double-click Start_Windows.bat. Your browser opens at http://localhost:8501. Keep the console running; closing it stops the app.

On Linux/macOS:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.address 127.0.0.1
```

## Features
- OpenNGC NGC/IC catalog and Messier cross-references, including addendum objects M40 and M45. M102 uses NGC5866 as an explicit planner convention; its historical identification is disputed. Both CSVs are bundled; missing files are downloaded and cached in data/. No fabricated fallback catalog.
- Editable latitude, longitude, location name and IANA time zone. Foley is the default. Save location persists your choice. Longitude west is negative. Change the time zone when traveling; it is not inferred from coordinates.
- Selected evening date covers local noon through next local noon. Astronomical darkness, minimum altitude, optional southern obstruction, Moon separation, Moon-free hours, best continuous window and altitude chart. Local time includes DST.
- Search, catalog/type/status filters, at least-two-hour filter and CSV export.
- Persistent Imaged / Needs reimage checkboxes, first imaging date, personal image link and notes. Messier and NGC aliases share the same OpenNGC object record. No objects are premarked as completed. M31 and NGC869 can be marked Needs reimage.
- Three online survey reference views per object: DSS2 detail, DSS2 wide field and 2MASS infrared. These are not three independently curated photographs. Some survey coverage is missing or images may fail to load; links let you open them separately. Full professional/amateur photo curation is not bundled.
- Astrospheric v2 forecast integration, activated with your private API key. Calls consume provider credits. The key is saved locally in data/astrospheric_api_key.txt and loaded on restart. Clear the sidebar field to forget it. Forecast is shown separately from geometric visibility; no invented combined quality score.

## Data and limitations
Coordinates are transformed from ICRS with Astropy's built-in solar-system ephemeris, offline Earth orientation tables, and geometric (unrefracted) altitudes. Windows have approximately five-minute sampling precision; weather and exact skyline mapping do not change the geometric ranking. The simple southern obstruction covers azimuth 90–270 degrees. No telescope field-of-view/framing model is included in this first version.

OpenNGC can include duplicate designations, non-existent catalog entries and non-imaging object types. Entries without coordinates are excluded. NGC and IC are supplied together; use the catalog filter to choose. Initial download and images require internet access. The full catalog calculation takes longer than Messier; results are cached while the app is running.

Records are stored in data/imaging.sqlite3; settings in data/settings.json. Back up the entire data directory to preserve records. CSV backup exports records but automatic CSV restoration is not yet supplied.

Sources: https://github.com/mattiaverga/OpenNGC (catalog data CC BY-SA 4.0; upstream authors/contributors). Cached CSVs remain under that license. https://alasky.cds.unistra.fr/hips-image-services/hips2fits (CDS survey cutout service). https://www.astrospheric.com/DynamicContent/api_info_v2 (forecast API). Individual survey imagery retains its provider attribution and terms. Application source is provided for personal modification.

Forecast repair: empty responses now show an error; provider errors are preserved and timestamps validated. To update an existing installation, stop the app and replace only app.py and core.py from this package. Keep your existing data folder to preserve imaging records. Restart Start_Windows.bat, re-enter the key and refresh the forecast.

Weather temperatures and dew points display and export in Fahrenheit; wind displays and exports in mph. API keys are private to your local installation and are never included in distributed packages.

Check Explore in the target table to update the details, chart, gallery, and imaging form. The dropdown also remains available. Tonight’s plan checkboxes in the table are editable and save immediately.

Select an object and use Add to tonight’s plan to save it automatically for the selected observing date. Uncheck to remove it. Expand Tonight’s plan to view saved targets and export their observing windows. Plans persist locally in imaging.sqlite3.

Export tonight’s plan downloads only checked targets for the selected date, including chosen targets hidden by search filters. Export all displayed targets downloads the full current table.

PDF plans: click Generate tonight’s plan PDF, then Download tonight’s plan PDF. Each checked target gets an embedded survey image, a brief description, catalog details and local observing windows. Descriptions are based on object type, with specific descriptions for M110 and M33. Images require internet during generation; the saved PDF works offline. The opening overview includes available Astrospheric weather, Sun/Moon rise and set, twilight and approximate Moon illumination. To update: copy app.py, plan_pdf.py, requirements.txt and the fonts folder into the existing installation, preserving data; run Start_Windows.bat to install the new PDF dependency.

Night overview update: copy app.py, plan_pdf.py and night_summary.py into your installation. Generate PDF refreshes Astrospheric weather using the saved API key and consumes the provider’s normal API credits. Forecast rows cover 6 PM through roughly 6 AM in local time; unavailable coverage is labeled. Keep the fonts folder and your data folder.

Imaging guidance: targets now show a transparent heuristic SeeStar suitability rating, configurable approximate frame dimensions, Moon interference and phase, filter guidance, and estimated accepted stacked exposure. The PDF adds a guidance page after each target image/details page. These are planning estimates, not calibrated exposure predictions; field rotation, rejection rate, light pollution and actual surface brightness affect results. To update copy app.py, plan_pdf.py and imaging_guidance.py into the installation. Preserve data and fonts.
