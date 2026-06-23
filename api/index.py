import os
import html
import json
import urllib.parse
import httpx
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# 1. Fetch your secrets directly from Vercel Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_BASE_URL = os.environ.get("API_BASE_URL")

# Initialize FastAPI (for Vercel serverless) and Telegram Bot
app = FastAPI()
ptb = ApplicationBuilder().token(BOT_TOKEN).build()

async def vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check for arguments
    if not context.args:
        await update.message.reply_text("⚠️ Please provide a vehicle number. Example: /vehicle MH12XX1234")
        return

    # Send initial status message
    status_msg = await update.message.reply_text(
        "Searching vehicle database... Please wait ⏳\n*(Note: This may take up to 60s if the database is waking up)*", 
        parse_mode="Markdown"
    )

    # Use the Secret API Base URL instead of hardcoding it
    vehicle_number = "".join(context.args) 
    encoded_query = urllib.parse.quote(vehicle_number)
    url = f"{API_BASE_URL}{encoded_query}"

    try:
        # 60s timeout for Render cold starts
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)

        if response.status_code != 200:
            await status_msg.edit_text(f"⚠️ Error: The server returned a {response.status_code} status code. Please try again later.")
            return

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            safe_fallback = html.escape(response.text.strip())
            await status_msg.edit_text(f"⚠️ Raw Response (Failed to parse JSON):\n<code>{safe_fallback}</code>", parse_mode="HTML")
            return

        if isinstance(data, dict):
            # Explicitly remove hidden/status keys
            keys_to_remove = ["powered_by", "api_info", "status", "code", "message", "developer"]
            for key in keys_to_remove:
                data.pop(key, None)

            if not data:
                await status_msg.edit_text("⚠️ No vehicle details found.")
                return

            # Formatting array
            output_lines = [
                "📋 <b>VEHICLE DETAILS REPORT</b>",
                "━━━━━━━━━━━━━━━━━━━━━━━━"
            ]
            
            # Recursive function to unpack nested dictionaries line-by-line
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

            # Add parsed data to output
            output_lines.extend(parse_dict(data))

            # Custom Private Database Footer
            output_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
            output_lines.append("🗄️ <b>Private Database</b>")
            output_lines.append("👤 <b>Owner:</b> @souvik_halla")

            await status_msg.edit_text("\n".join(output_lines), parse_mode="HTML")
            
        else:
            safe_dump = html.escape(str(data))
            await status_msg.edit_text(f"⚠️ Unexpected Data Format:\n<code>{safe_dump}</code>", parse_mode="HTML")

    except httpx.TimeoutException:
        await status_msg.edit_text("⚠️ <b>Timeout Error:</b> The database took too long to respond. It was likely waking up from sleep. <b>Please run the command again right now!</b>", parse_mode="HTML")
    except httpx.RequestError as e:
        await status_msg.edit_text(f"⚠️ <b>Network Error:</b> Could not reach the API.\nDetails: <code>{html.escape(str(e))}</code>", parse_mode="HTML")
    except Exception as e:
        await status_msg.edit_text(f"⚠️ <b>Unexpected Error:</b>\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")

# Register the command
ptb.add_handler(CommandHandler("vehicle", vehicle))

# 3. Webhook Endpoint for Vercel
@app.post("/api/index")
async def process_update(request: Request):
    # CRITICAL: Initialize AND start the bot in the serverless environment
    if not ptb._initialized:
        await ptb.initialize()
        await ptb.start() 
    
    # Parse the incoming JSON from Telegram and process it
    try:
        req_json = await request.json()
        update = Update.de_json(req_json, ptb.bot)
        await ptb.process_update(update)
    except Exception as e:
        print(f"Error processing update: {e}")
        
    return {"ok": True}
