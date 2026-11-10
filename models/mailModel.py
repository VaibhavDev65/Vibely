import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def login_otp(receiver_email, EMAIL_SENDER, EMAIL_PASSWORD, otp):
    sender_email = EMAIL_SENDER
    sender_password = EMAIL_PASSWORD  # Gmail App Password use karein
    
    # Message container setup
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your Verification Code (OTP)"
    msg["From"] = sender_email
    msg["To"] = receiver_email
    otp_code = otp  # Use the provided OTP instead of generating a new one
    
    # Professional HTML & Inline CSS Design
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f7f9fc; margin: 0; padding: 40px 15px;">
      
      <!-- Main Container Card -->
      <div style="max-width: 520px; background: #ffffff; padding: 40px 30px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05); margin: 0 auto; border: 1px solid #eaeaea;">
        
        <!-- Header Logo & Subtitle -->
        <div style="text-align: center; margin-bottom: 30px;">
          <h1 style="margin: 0; font-size: 38px; font-weight: 800; background: linear-gradient(135deg, #e91e63 0%, #8e24aa 50%, #3f51b5 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; color: #ffffff;">Vibely</h1>
          <p style="margin: 6px 0 0 0; font-size: 20px; font-weight: 700; color: #111111; letter-spacing: -0.2px;">One time password</p>
        </div>
        
        <!-- Body Content -->
        <h2 style="color: #2c3e50; font-size: 20px; font-weight: 700; margin-top: 0; margin-bottom: 12px;">Account Verification</h2>
        
        <p style="color: #555555; font-size: 15px; margin: 0 0 8px 0;">Hello,</p>
        <p style="color: #555555; font-size: 15px; line-height: 1.6; margin: 0 0 25px 0;">
          Use the following One-Time Password (OTP) to complete your login or registration. Do not share this code with anyone.
        </p>
        
        <!-- OTP Highlight Box with Linear Gradient -->
        <div style="text-align: center; margin: 35px 0;">
          <div style="display: inline-block; background: linear-gradient(135deg, #ff416c 0%, #8a2387 50%, #7a00cc 100%); padding: 16px 36px; border-radius: 12px; box-shadow: 0 6px 20px rgba(138, 35, 135, 0.3);">
            <span style="font-size: 32px; font-weight: 800; color: #ffffff; letter-spacing: 8px; font-family: monospace;">{otp_code}</span>
          </div>
        </div>
        
        <!-- Footer Info -->
        <p style="color: #777777; font-size: 13px; line-height: 1.5; text-align: center; margin-top: 30px; margin-bottom: 0;">
          This code is valid for <strong>10 minutes</strong>. If you didn't request this, please ignore this email.
        </p>
        
      </div>
    </body>
    </html>
    """
    
    # Attach HTML content to message
    msg.attach(MIMEText(html_content, "html"))
    
    # Connect to SMTP Server and Send Mail with exception raising
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("OTP Email sent successfully!")
        return otp_code  
    
    except Exception as e:
        print(f"Error sending email: {e}")
        raise e  # Flask server ko exact error pass karne ke liye exception raise karein

if __name__ == "__main__":
    receiver_email = "as0883443@gmail.com"
    EMAIL_SENDER = "vibelysupport01@gmail.com"
    EMAIL_PASSWORD = "acvjueykucidlcut"
    otp = "123456"
    try:
        login_otp(receiver_email, EMAIL_SENDER, EMAIL_PASSWORD, otp)
    except Exception as e:
        print(f"Test execution failed: {e}")