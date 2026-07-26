# 🚀 Server Deployment Guide (Oracle Cloud / VPS)

Run the **AI Caller** 24/7 on a cloud server so it answers phone calls even when your laptop is turned off.

---

## 1. Get a Free Cloud Server
You can use **Oracle Cloud Always Free** (VM.Standard.A1.Flex or E2.1.Micro) or any cheap VPS (DigitalOcean $4/mo, AWS EC2, Hetzner):
- **OS**: Ubuntu 22.04 or 24.04 LTS

---

## 2. Deploy in 3 Commands

1. **Clone the repo on your server**:
   ```bash
   git clone https://github.com/Satya-s89/ai-caller.git
   cd ai-caller
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   nano .env
   # Add your GROQ_API_KEY, SARVAM_API_KEY, and LIVEKIT credentials
   ```

3. **Run automated setup**:
   ```bash
   chmod +x deploy/setup.sh
   ./deploy/setup.sh
   ```

4. **Start the 24/7 service**:
   ```bash
   sudo systemctl start ai-caller
   ```

---

## 3. Useful Commands

- **Check server status**:
  ```bash
  sudo systemctl status ai-caller
  ```

- **View live logs**:
  ```bash
  journalctl -u ai-caller -f
  ```

- **Restart service**:
  ```bash
  sudo systemctl restart ai-caller
  ```

- **Access Live Dashboard**:
  Open `http://<your-server-ip>:3000` in your browser.
