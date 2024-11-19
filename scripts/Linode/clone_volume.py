import subprocess
import json

def delete_linode_volume_by_label(label):
    # Check if a volume with the specified label exists
    list_command = f"linode-cli volumes list --label {label} --json"
    existing_volume_info = subprocess.check_output(list_command, shell=True)
    existing_volume_info = json.loads(existing_volume_info.decode())

    if existing_volume_info:
        # If the volume exists, delete it
        volume_id = existing_volume_info[0]['id']
        print(f"Vouleme is found with ID: {volume_id}")
        
        delete_command = f"linode-cli volumes delete {volume_id}"
        subprocess.run(delete_command, shell=True)
        print(f"Deleted existing volume with label '{label}' (Volume ID: {volume_id})")

def clone_linode_volume(volume_id, new_label):
    # Delete existing volume with the same label if it exists
    delete_linode_volume_by_label(new_label)

    # Run the command to clone the volume
    clone_command = f"linode-cli volumes clone {volume_id} --label {new_label}"
    subprocess.run(clone_command, shell=True)
    print(f"Cloned volume {volume_id} to a new volume with label '{new_label}'")

# Example usage:
gs_volume_id = "1841546"  # origial domain-jenkins volume
clone_linode_volume(volume_id=gs_volume_id, new_label="MountPoint100GB-Jenkins-Clone")
