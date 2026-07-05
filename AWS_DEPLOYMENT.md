# Deploying Agent WAF to AWS EC2

This guide outlines how to deploy the Agent WAF to an AWS EC2 `t3.small` instance.

## 1. Launch the EC2 Instance

1. Navigate to the **EC2 Dashboard** in AWS and click **Launch Instance**.
2. **Name**: `Agent-WAF-Prod`
3. **AMI**: Amazon Linux 2023 or Ubuntu 24.04 LTS (Ubuntu recommended).
4. **Instance Type**: `t3.small` (2 vCPU, 2GB RAM).
5. **Key Pair**: Select or create a new `.pem` key pair for SSH access.
6. **Network Settings**:
   - Auto-assign Public IP: Enable
   - Create a new Security Group with the following Inbound Rules:
     - `SSH (22)` from `Anywhere` (or your IP)
     - `HTTP (80)` from `Anywhere` (Allows access to the WAF proxy/dashboard)

Click **Launch Instance**.

## 2. Connect and Install Docker

SSH into your new instance:
```bash
ssh -i /path/to/your-key.pem ubuntu@<your-ec2-public-ip>
```

Install Docker and Docker Compose:
```bash
# Update packages
sudo apt-get update -y

# Install Docker
sudo apt-get install -y docker.io docker-compose

# Start Docker and enable it on boot
sudo systemctl start docker
sudo systemctl enable docker

# Give the default 'ubuntu' user permissions to run docker commands
sudo usermod -aG docker ubuntu

# LOG OUT AND LOG BACK IN for the group changes to take effect
exit
```

Reconnect to the server:
```bash
ssh -i /path/to/your-key.pem ubuntu@<your-ec2-public-ip>
```

## 3. Clone and Deploy

Clone your repository (assuming you have pushed this code to a Git repository):
```bash
git clone <your-repo-url>
cd Agent-WAF
```

Run the deployment script:
```bash
./deploy.sh
```

## 4. Verification

Once the script completes, the containers will be running in the background.

1. **Dashboard**: Open your browser and navigate to `http://<your-ec2-public-ip>`
2. **API Testing**: Send a POST request to test the WAF.

```bash
curl -X POST "http://<your-ec2-public-ip>/api/v1/proxy" \
  -H "Content-Type: application/json" \
  -H "X-Target-URL: https://mock.internal.tool" \
  -H "X-Agent-Scope: You are a customer support agent." \
  -d '{
    "tool_name": "RunSystemCommand",
    "parameters": {"cmd": "cat /etc/passwd"}
  }'
```

You should receive a `403 Forbidden` response blocking the semantic drift/injection!

## Maintenance

To pull new code updates and restart the server, simply run:
```bash
./deploy.sh
```

If you ever need to view the live logs:
```bash
docker-compose -f docker-compose.prod.yml logs -f
```
