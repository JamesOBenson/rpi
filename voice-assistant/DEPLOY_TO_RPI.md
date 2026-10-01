# Deploy to Raspberry Pi 5

## Transfer Project to RPi

```bash
# From your Mac, copy to RPi
scp -r ~/voice-assistant pi@<RPI_IP_ADDRESS>:~/voice-assistant

# Or use rsync for better transfer
rsync -avz --progress ~/voice-assistant/ pi@<RPI_IP_ADDRESS>:~/voice-assistant/
```

## On Raspberry Pi

```bash
# SSH into RPi
ssh pi@<RPI_IP_ADDRESS>

# Navigate to project
cd ~/voice-assistant

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Download models (on RPi)
./download_models.sh

# Run
cd src
python main.py
```

## Hailo-9L Integration (Optional)

```bash
# Install Hailo SDK
sudo apt install -y hailo-rt

# Enable Hailo acceleration
# See: https://docs.hailo.ai/
```

## Auto-start on Boot

```bash
# Create systemd service
sudo nano /etc/systemd/system/stembuddy.service
```

```ini
[Unit]
Description=STEM Buddy Voice Assistant
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/voice-assistant
ExecStart=/home/pi/voice-assistant/venv/bin/python src/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable service
sudo systemctl enable stembuddy.service
sudo systemctl start stembuddy.service
```

## Troubleshooting

### Audio Issues
```bash
# Check audio devices
arecord -l
aplay -l

# Set default device
sudo nano /usr/share/alsa/alsa.conf
```

### GPIO Permissions
```bash
# Add user to gpio group
sudo usermod -a -G gpio pi
sudo usermod -a -G video pi
# Log out and back in
```

### Model Loading
```bash
# Check models exist
ls -lh models/

# Verify model integrity
# Re-download if corrupted
```