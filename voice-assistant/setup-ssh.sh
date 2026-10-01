#!/bin/bash
#
# Setup SSH connection to RPi from Mac
#

RPi_IP=""
RPi_USER="pi"

echo "🔌 RPi SSH Setup"
echo "================"
echo ""
echo "Enter your RPi's IP address:"
read RPi_IP

if [ -z "$RPi_IP" ]; then
    echo "❌ No IP provided"
    exit 1
fi

echo ""
echo "Testing connection to $RPi_USER@$RPi_IP..."

# Test connection
if ssh -o ConnectTimeout=5 -o BatchMode=yes $RPi_USER@$RPi_IP exit 2>/dev/null; then
    echo "✅ Connected!"
else
    echo "⚠️  Cannot connect. Make sure:"
    echo "   1. RPi is powered on"
    echo "   2. RPi is on same network"
    echo "   3. IP address is correct"
    echo ""
    read -p "Try anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Setup SSH key
echo ""
echo "Setting up SSH key authentication..."
ssh-copy-id $RPi_USER@$RPi_IP

# Create sync script
echo ""
echo "Creating sync script..."
cat > ~/sync-to-rpi.sh << EOF
#!/bin/bash
# Sync voice-assistant to RPi
rsync -avz --progress ~/voice-assistant/ $RPi_USER@$RPi_IP:~/voice-assistant/
EOF

chmod +x ~/sync-to-rpi.sh

echo ""
echo "✅ Setup complete!"
echo ""
echo "Commands:"
echo "  SSH to RPi:    ssh $RPi_USER@$RPi_IP"
echo "  Sync files:    ~/sync-to-rpi.sh"
echo "  View logs:     ssh $RPi_USER@$RPi_IP 'tail -f ~/voice-assistant/logs/buddy.log'"
echo ""