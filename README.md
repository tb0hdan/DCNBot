-----

## Meshtastic-Telegram revised: Documentation
 
### **Overview**

This project is a powerful, two-way gateway that bridges a Meshtastic (LoRa) radio network with a Telegram chat group. It allows users on a remote, off-grid Meshtastic network to send and receive text messages from users on the internet via Telegram, and vice-versa.

The gateway is designed to run 24/7 as a reliable, hands-off server application, but it also includes a command-line interface for direct interaction with the mesh.

### **Key Features** 🚀

  * **Two-Way Messaging**: Seamlessly relays messages from Meshtastic to Telegram and from Telegram to Meshtastic.
  * **Command-Based Forwarding**: Telegram users can send broadcast messages with `/send` and private direct messages with `/dm`, giving them full control over what gets sent to the radio network.
  * **Dynamic Node Naming**: Automatically learns and stores the friendly names of nodes on the mesh (e.g., "Jay," "dcn1") and uses them in Telegram. For unknown nodes, it displays a clear hexadecimal ID (e.g., `[!7f4dbc79]`).
  * **Automated Welcome DMs**: Can be configured to automatically send a welcoming direct message to new nodes the first time they are heard on the mesh.
  * **Robust Message Handling**: Automatically splits long messages from Telegram into multiple, numbered chunks that are suitable for the small packet size of the Meshtastic network.
  * **Powerful Command-Line Interface (CLI)**: Directly send broadcast messages, DMs, and list all known nodes from your server's command line, independent of the Telegram bridge.
  * **Secure & Configurable**: Works with encrypted channel traffic and allows you to independently enable or disable each direction of the relay in the configuration file.

-----

### **Requirements**

1.  **Hardware**:
      * A Meshtastic device configured to act as an MQTT gateway.
      * A server or computer to run the gateway script (e.g., a Raspberry Pi or a small cloud server running Linux).
2.  **Software**:
      * An MQTT broker (like Mosquitto).
      * Python 3.8+
      * A Telegram account and a Telegram Bot token.

-----

### **Setup Instructions**

Follow these steps to get the gateway running.

#### **Step 1: Configure Your Meshtastic MQTT Gateway**

Ensure your Meshtastic device is correctly configured to talk to your MQTT broker. In your device's **MQTT** module settings:

  * Set the **MQTT server address, username, and password**.
  * Ensure **`JSON enabled`** is **turned off (disabled)**.

#### **Step 2: Prepare the Server**

1.  Get the project code onto your server.
2.  Create and activate a Python virtual environment.
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  Create a `requirements.txt` file with the necessary libraries:
    ```
    # requirements.txt
    aiomqtt
    python-telegram-bot
    cryptography
    pysqlite3
    ```
4.  Install the libraries:
    ```bash
    pip install -r requirements.txt
    ```

#### **Step 3: Create the `config.ini` File**

Create a file named `config.ini` and paste the following content into it, filling it out with your own details.

```ini
# config.ini

[telegram]
api_key = YOUR_TELEGRAM_BOT_API_KEY_HERE
chat_id = YOUR_TELEGRAM_CHAT_ID_HERE

[mqtt]
host = your_mqtt_broker_address
port = 1883
user = your_mqtt_username
password = your_mqtt_password

[relay]
meshtastic_to_telegram_enabled = true
telegram_to_meshtastic_enabled = true

[welcome_message]
enabled = true
message = Welcome to the mesh! This is an automated message from the Telegram gateway.

[database]
path = ./meshtastic.sqlite
```

-----

### **Running the Gateway**

You can run the gateway as a 24/7 service or interact with it directly using the new command-line interface.

#### **1. As a 24/7 Service**

To run the full Telegram bridge continuously, set it up as a `systemd` service.

  * Create a service file: `sudo nano /etc/systemd/system/meshtastic-gateway.service`

  * Paste in the following, **updating the `User` and paths** to match your setup.

    ```ini
    [Unit]
    Description=Meshtastic to Telegram Gateway
    After=network.target

    [Service]
    User=dcn1
    WorkingDirectory=/home/dcn1/Documents/meshtastic-telegram-gateway
    ExecStart=/home/dcn1/Documents/meshtastic-telegram-gateway/venv/bin/python -m mtg.gateway
    Restart=always
    RestartSec=5

    [Install]
    WantedBy=multi-user.target
    ```

  * Enable and start the service:

    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable meshtastic-gateway.service
    sudo systemctl start meshtastic-gateway.service
    ```

#### **2. Using the Command-Line Interface (CLI) ⌨️**

The CLI allows you to send messages and manage nodes directly from your server's terminal, without interacting with Telegram.

  * **List All Known Nodes**
    This command displays a formatted table of all nodes stored in the database.

    ```bash
    python -m mtg.cli nodes
    ```

  * **Send a Broadcast Message**
    This sends a message to everyone on the mesh. The message appears to come from the gateway node itself.

    ```bash
    python -m mtg.cli send This is a test broadcast from the command line.
    ```

  * **Send a Direct Message (DM)**
    This sends a private message to a specific node using its name or hex ID.

    ```bash
    # By name
    python -m mtg.cli dm Jay Hello from the CLI!

    # By hex ID
    python -m mtg.cli dm !da5c80d4 This is a direct message via hex ID.
    ```
