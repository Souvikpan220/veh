import os
import html
import json
import urllib.parse
import httpx
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_BASE_URL = os.environ.get("API_BASE_URL")

app = FastAPI()
ptb = ApplicationBuilder().token(BOT_TOKEN).build()

async def vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("🚀 COMMAND TRIGGERED: /vehicle")
    if not context.args:
        await update.message.reply_text("⚠️ Please provide a vehicle number. Example: /vehicle MH12XX1234")
        return

    status_msg = await update.message.reply_text(
        "Searching vehicle database... Please wait ⏳\n*(Note: This may take up to 60s if the database is waking up)*", 
        parse_mode="Markdown"
    )

    vehicle_number = "".join(context.args) 
    encoded_query = urllib.parse.quote(vehicle_number)
    url = f"{API_BASE_URL}{encoded_query}"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)

        if response.status_code != 200:
            await status_msg.edit_text(f"⚠️ Error: The server returned a {response.status_code} status code.")
            return

        data = json.loads(response.text)
        
        if isinstance(data, dict):
            keys_to_remove = ["powered_by", "api_info", "status", "code", "message", "developer"]
            for key in keys_to_remove:
                data.pop(key, None)

            if not data:
                await status_msg.edit_text("⚠️ No vehicle details found.")
                return

            output_lines = ["📋 <b>VEHICLE DETAILS REPORT</b>", "━━━━━━━━━━━━━━━━━━━━━━━━"]
            
            def parse_dict(d, indent=""):
                lines = []
                for k, v in d.items():
                    clean_k = k.replace("_", " ").title()
                    escaped_k = html.escape(clean_k)
                    if isinstance(v, dict):
                        lines.append(f"{indent}📁 <b>{escaped_k}:</b>")
                        lines.extend(parse_dict(v, indent + "   ↳ "))
                    else:
                        val_str = str(v).strip()
                        escaped_v = html.escape(val_str) if val_str else "N/A"
                        lines.append(f"{indent}🔹 <b>{escaped_k}:</b> <code>{escaped_v}</code>")
                return lines

            output_lines.extend(parse_dict(data))
            output_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
            output_lines.append("🗄️ <b>Private Database</b>")
            output_lines.append("👤 <b>Owner:</b> @souvik_halla")

            await status_msg.edit_text("\n".join(output_lines), parse_mode="HTML")
        else:
            await status_msg.edit_text("⚠️ Unexpected Data Format.")

    except Exception as e:
        print(f"❌ ERROR IN COMMAND: {e}")
        await status_msg.edit_text(f"⚠️ <b>Error:</b>\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")

ptb.add_handler(CommandHandler("vehicle", vehicle))

# --- NEW DEBUG ROUTES ---

# 1. Health Check Route (For your browser)
@app.get("/")
@app.get("/api/index")
async def root():
    return {"status": "ALIVE", "message": "The Vercel Server is running perfectly!"}

# 2. Webhook Route
@app.post("/api/index")
async def process_update(request: Request):
    print("🔔 INCOMING WEBHOOK FROM TELEGRAM!")
    try:
        if not ptb._initialized:
            print("⚙️ Initializing bot...")
            await ptb.initialize()
            await ptb.start()
            
        req_json = await request.json()
        print(f"📦 Payload: {req_json}") # This shows us if Telegram sent the message
        
        update = Update.de_json(req_json, ptb.bot)
        await ptb.process_update(update)
        print("✅ Update processed successfully.")
    except Exception as e:
        print(f"❌ WEBHOOK CRASHED: {e}")
        
    return {"ok": True}
