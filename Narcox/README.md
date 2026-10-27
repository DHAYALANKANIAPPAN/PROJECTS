# NarcoX - Law Enforcement Intelligence Platform

**Techraga '26 Hackathon Prototype** (Theme 1: Intelligent Systems)

NarcoX is an AI platform designed to detect online drug trafficking on public Telegram and Instagram channels, presenting actionable alerts on a live investigator dashboard.

## Architecture
- **Frontend**: Plain HTML/JS hosted statically on Vercel.
- **Backend**: Node.js Serverless Functions (`api/`) hosted on Vercel.
- **Database**: MongoDB Atlas (NoSQL) for storing JSON alert documents.
- **Data Ingestion**: Real-time webhooks from Telegram and Instagram.

## Local Setup
1. Clone the repo: `git clone https://github.com/your-org/narcox.git`
2. Install dependencies: `npm install`
3. Add a `.env` file with your credentials (see `.env.example`).
4. Run locally: `npx serve public` for frontend.

## Environment Variables
- `MONGODB_URI`: Connection string for Atlas cluster.
- `TELEGRAM_BOT_TOKEN` & `TELEGRAM_WEBHOOK_SECRET`: For Telegram bot integration.
- `IG_VERIFY_TOKEN` & `IG_PAGE_ACCESS_TOKEN`: For Instagram Graph API.
- `GEMINI_API_KEY`: For AI text/image analysis.

## Demo Steps
1. Navigate to the live dashboard at `https://narcox.vercel.app`.
2. View the real-time polling of alerts.
3. Click "Evidence" to see cryptographic hashing in action.
4. Click "Network Map" to explore entity relationships.

<!-- Deployment pipeline verified -->
