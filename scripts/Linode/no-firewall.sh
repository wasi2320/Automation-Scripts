#!/bin/bash

# Google Chat Webhook URL
google_chat_webhook_url='https://chat.googleapis.com/v1/spaces/AAAAVm58MNw/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=lavdyE8b_okfmb8KKAl_dwWHN424IvA-OkM9o9QvRh4'

# Fetch all Linodes (servers)
all_linodes=$(linode-cli linodes list --format "id,label" --no-header --text)

# Check if linodes data is available
if [ -z "$all_linodes" ]; then
    echo "No Linodes found."
    exit 1
fi

# Fetch all firewalls
firewalls=$(linode-cli firewalls list --format "id" --no-header --text)

# Initialize an array to store Linodes that are behind firewalls
firewalled_linodes=()

# Loop through each firewall and get associated Linodes
while IFS= read -r firewall_id; do
    # Fetch Linodes behind the firewall
    firewall_devices=$(linode-cli firewalls devices-list $firewall_id --format "entity.id" --no-header --text)

    # Append the Linodes behind this firewall to the firewalled_linodes array
    firewalled_linodes+=($firewall_devices)
done <<< "$firewalls"

# Convert the firewalled_linodes array to a unique set (remove duplicates)
firewalled_linodes_unique=($(echo "${firewalled_linodes[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' '))

# Prepare the message for Google Chat
message="Linodes not behind any firewall:\\n"
alert_sent=false  # Flag to check if alert has been sent

while IFS= read -r linode; do
    linode_id=$(echo "$linode" | awk '{print $1}')
    linode_label=$(echo "$linode" | awk '{print $2}')

    # Check if the Linode ID is in the firewalled_linodes array
    if [[ ! " ${firewalled_linodes_unique[@]} " =~ " ${linode_id} " ]]; then
        message+="ID: $linode_id, Label: $linode_label\\n"
        alert_sent=true  # Set the flag to true if a Linode is found
    fi
done <<< "$all_linodes"

# Send the message to Google Chat webhook only if there are Linodes not behind a firewall
if $alert_sent; then
    # Format the message into a JSON payload for Google Chat
    json_payload=$(jq -n --arg text "$message" '{text: $text}')

    # Send the message to Google Chat webhook
    curl -X POST -H "Content-Type: application/json" -d "$json_payload" "$google_chat_webhook_url"
else
    echo "No Linodes found that are not behind a firewall."
fi

