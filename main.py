'''
Copyright 2020 Google, LLC.
'''
# basics
import os
import h5py
import mfid
import logging
from pathlib import Path
from cloudevents.http import from_http
from flask import Flask, request

# crucible
from crucible import CrucibleClient
from crucible.models import Dataset

CRUCIBLE_API_URL = os.environ.get("CRUCIBLE_API_URL")
CRUCIBLE_API_KEY = os.environ.get("CRUCIBLE_API_KEY")

client = CrucibleClient(CRUCIBLE_API_URL, CRUCIBLE_API_KEY)

# other constants
EXCLUDE_FILES_FORMATS = [".pyc", ".pyo", ".pyd", ".db", ".sqlite",".ini"]
SCOPEFOUNDRY_INSTRUMENTS = ["aldbot", "hip_microscope", "qspleem", "spinbot", 'supracl_microscope']

# logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# app!
app = Flask(__name__)

@app.route("/", methods=["POST"])
def index():

    # Create a CloudEvent object from the incoming request
    event = from_http(request.headers, request.data)

    # Run the process you want on event detection
    dsfile = event.data.get('name')
    logger.info(f'received {dsfile=}')
    instrument = dsfile.split("/")[0]
    logger.info(f'instrument parsed as: {instrument}')

    if any([dsfile.endswith(fmt) for fmt in EXCLUDE_FILES_FORMATS]):
        message = f"File {dsfile} is excluded from processing due to its format."
        logger.warning(message)
        return message, 200

    if 'api-uploads' in dsfile:
        message = f"File {dsfile} is an API upload and will not be processed."
        logger.warning(message)
        return message, 200
    
    try:
        parsed_dsid = None
        cloudpath = os.path.join('/gcs/mnt', dsfile)

        if dsfile.endswith(".h5") and instrument in SCOPEFOUNDRY_INSTRUMENTS:
            # these instruments need to pass in the unique id
            logger.info('extracting unique_id...')
            with h5py.File(cloudpath, 'r') as h5file:
                parsed_dsid = h5file.attrs.get('unique_id')
            logger.info(f'# ============= {parsed_dsid=}')

        if instrument == 'ALS-BL12012' and not dsfile.endswith(".zip"):
            message = f'Skipping unzipped RGA file: {dsfile=}, {event['id']=}'
            logger.info(message)
            return message, 200
        elif instrument == 'ALS-BL12012':
            new_rga_dsname = Path(dsfile).stem
            found_ds = client.datasets.list(dataset_name = new_rga_dsname)
            if len(found_ds) > 0:
                dsid = found_ds[-1]['unique_id']
            else:
                dsid, _ = mfid.mfid()
                
            base_ds = Dataset(unique_id = dsid,
                        dataset_name = new_rga_dsname,
                        instrument_name = "ALS-BL12012",
                        measurement = "automated_RGA_TEY_batch_run",
                        data_type = "automated_RGA_TEY_batch_run",
                        project_id = "10k_perovskites")
        else:
            logger.info('creating dataset...')
            base_ds = Dataset(unique_id = parsed_dsid)

        new_ds = client.datasets.create(base_ds, files_to_upload = [cloudpath])
        dsid = new_ds['created_record']['unique_id']

        message = f"{dsfile=}, {event['id']=}, message: dataset created with {dsid=}"
        logger.info(message)
        return message, 200
    
    except Exception as error:
        message = f"{dsfile=}, {event['id']=}, failed with {error=}"
        logger.exception(message)
        return message, 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
