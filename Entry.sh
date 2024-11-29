#!/bin/bash

# Function to install required packages
install_packages() {
    sudo apt-get update
    sudo apt-get install -y curl wget zip unzip jq
    if ! command -v pip &> /dev/null; then
        sudo apt-get install -y python3-pip
    fi
    if ! command -v Xvfb &> /dev/null; then
        sudo apt-get install -y xvfb
    fi
}

# Function to install Python dependencies from requirements.txt
install_python_dependencies() {
    if [ -f "requirements.txt" ]; then
        if command -v pip &> /dev/null; then
            pip install -r requirements.txt
        elif command -v pip3 &> /dev/null; then
            pip3 install -r requirements.txt
        else
            echo "pip is not installed. Please install pip or pip3."
            exit 1
        fi
    else
        echo "requirements.txt not found. Skipping Python dependencies installation."
    fi
}

# Function to kill all related processes
kill_related_processes() {
    pkill -f "python /app/main.py"
    pkill -f chrome
    pkill -f undetected_chromedriver
}

# Function to display IP and system information
display_ip_info() {
    IP_INFO=$(curl -s ipinfo.io)
    IP=$(echo $IP_INFO | jq -r '.ip')
    ISP=$(echo $IP_INFO | jq -r '.org')
    COUNTRY=$(echo $IP_INFO | jq -r '.country')
    REGION=$(echo $IP_INFO | jq -r '.region')
    CITY=$(echo $IP_INFO | jq -r '.city')
    HOSTNAME=$(hostname)
    echo "Hostname: $HOSTNAME"
    echo "IP Address: $IP"
    echo "ISP: $ISP"
    echo "Country: $COUNTRY"
    echo "Region: $REGION"
    echo "City: $CITY"
}

# Install required packages
install_packages

# Install Python dependencies
install_python_dependencies

# Remove temp file when previous execution crashed
rm -f /tmp/.X99-lock

# Set display port and dbus env to avoid hanging
# (https://github.com/joyzoursky/docker-python-chromedriver)
export DISPLAY=:99
export DBUS_SESSION_BUS_ADDRESS=/dev/null

# Display IP and system information
display_ip_info

# Start virtual display
Xvfb $DISPLAY -screen 0 1280x800x16 -nolisten tcp &

ls

# Download the zip file directly
curl -L -o /app/partial_session_data.zip "https://tvkkdata.tvkishorkumardata.workers.dev/download.aspx?file=sgkvf9%2BZuyMKdhm6w8iTNg6Ra%2BkIbbf58EugUIDxA%2FeORXWS6ozlpr%2F87o9LmMOw&expiry=Qmv7hfoZthakYWhme%2F5Y2w%3D%3D&mac=408bd4b62c66a7e2e90b67092e66a1798aca03a4895970efd5082d807e2270f0"
echo "Download completed."

sleep 15

ls

chmod 777 /app/partial_session_data.zip

sleep 15

# Check if the zip file exists and unzip it
if [ -f /app/partial_session_data.zip ]; then
    unzip -o /app/partial_session_data.zip -d /app/
    echo "First unzip completed."
    # Unzip the nested zip file
    unzip -o /app/partial_sessions.zip -d /app/
    echo "Second unzip completed."
    cd /app/app
    ls
    # Move the sessions folder to the correct location
    mv sessions /app/
    echo "Sessions folder moved successfully."
    # List the contents to verify
    ls -l /app/sessions
else
    echo "No session data zip file found."
fi

ls

sleep 15

# Kill all related processes
kill_related_processes

# Wait for 10 seconds
sleep 10

# Run the main Python script
python /app/main.py -cv 127 -v -g IN --proxy socks5://tvkk13579:5acb2fed98@209.200.249.208:12324

# Wait for 10 seconds
sleep 10

# Run the main Python script again
python /app/main.py -cv 127 -v -g IN --proxy socks5://tvkk13579:5acb2fed98@209.200.249.208:12324

# Kill all related processes again
kill_related_processes
