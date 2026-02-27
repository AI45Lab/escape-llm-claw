# Activate ELC venv
source .venv/bin/activate

# Generate AES-GCM encryption keys
python src/encoder.py 

# Run the ELC web server
python app.py
