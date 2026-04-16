import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import settings


class EmailService:

    def send_verification_code(self, to_email: str, code: str):
        """
        Send a 6-digit verification code to the given email address.
        If SMTP credentials are not configured, prints the code to the console
        (useful for local development without a real mail server).
        """
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            # Dev fallback: print code to terminal
            print(f"\n[EMAIL - DEV MODE] Verification code for {to_email}: {code}\n")
            return

        from_addr = settings.SMTP_FROM or settings.SMTP_USER

        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'AML Monitor – Email Verification Code'
        msg['From'] = from_addr
        msg['To'] = to_email

        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; background: #0F1117; color: #F1F5F9; padding: 40px;">
            <div style="max-width: 480px; margin: 0 auto; background: #1A1D27;
                        border-radius: 12px; padding: 32px; border: 1px solid #2D3748;">
              <div style="display: flex; align-items: center; margin-bottom: 24px;">
                <span style="font-size: 28px; margin-right: 12px;">🛡️</span>
                <div>
                  <h2 style="margin: 0; color: #F1F5F9;">AML Monitor</h2>
                  <p style="margin: 0; color: #64748B; font-size: 12px;">Transaction Monitoring System</p>
                </div>
              </div>

              <h3 style="color: #F1F5F9; margin-bottom: 8px;">Your Verification Code</h3>
              <p style="color: #94A3B8; font-size: 14px; margin-bottom: 24px;">
                Use the code below to complete your registration. It expires in
                <strong style="color: #F59E0B;">10 minutes</strong>.
              </p>

              <div style="background: #0F1117; border-radius: 8px; padding: 20px;
                          text-align: center; border: 1px solid #374151; margin-bottom: 24px;">
                <span style="font-size: 36px; font-weight: 700; letter-spacing: 10px;
                             color: #3B82F6;">{code}</span>
              </div>

              <p style="color: #64748B; font-size: 12px; margin: 0;">
                If you did not request this code, you can safely ignore this email.
              </p>
            </div>
          </body>
        </html>
        """

        msg.attach(MIMEText(html, 'html'))

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls(context=context)
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(from_addr, to_email, msg.as_string())
        except Exception as e:
            print(f"\n[EMAIL - SMTP ERROR] Could not send email: {e}")
            print(f"[EMAIL - DEV FALLBACK] Verification code for {to_email}: {code}\n")


    def send_welcome_credentials(self, to_email: str, full_name: str, username: str, password: str, role: str):
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            print(f"\n[EMAIL - DEV MODE] Welcome email for {to_email} | username: {username} | password: {password}\n")
            return

        from_addr = settings.SMTP_FROM or settings.SMTP_USER

        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Your AML Monitor Account Has Been Created'
        msg['From']    = from_addr
        msg['To']      = to_email

        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; background: #07090E; color: #E2E8F0; padding: 40px;">
            <div style="max-width: 500px; margin: 0 auto; background: #0E1119;
                        border-radius: 10px; padding: 32px;
                        border: 1px solid rgba(255,255,255,0.09);
                        border-top: 3px solid #F0A500;">

              <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 28px;">
                <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #F0A500, #C47D00);
                            border-radius: 8px; display: flex; align-items: center; justify-content: center;
                            font-size: 20px;">🛡️</div>
                <div>
                  <div style="font-size: 16px; font-weight: 800; color: #F1F5F9;">AML Monitor</div>
                  <div style="font-size: 10px; color: #F0A500; text-transform: uppercase; letter-spacing: 1px;">Compliance System</div>
                </div>
              </div>

              <h2 style="color: #F1F5F9; margin: 0 0 8px; font-size: 20px; letter-spacing: -0.3px;">
                Welcome, {full_name}!
              </h2>
              <p style="color: #64748B; font-size: 14px; margin: 0 0 28px; line-height: 1.6;">
                An account has been created for you on the <strong style="color: #E2E8F0;">AML Monitor</strong>
                transaction monitoring platform. Below are your login credentials.
              </p>

              <div style="background: #07090E; border: 1px solid rgba(255,255,255,0.08);
                          border-radius: 8px; padding: 20px; margin-bottom: 24px;">
                <p style="margin: 0 0 4px; font-size: 10px; color: #4B5563;
                           text-transform: uppercase; letter-spacing: 0.8px; font-weight: 700;">Your Credentials</p>

                <table style="width: 100%; border-collapse: collapse; margin-top: 14px;">
                  <tr>
                    <td style="padding: 8px 0; color: #4B5563; font-size: 13px; width: 110px;">Username</td>
                    <td style="padding: 8px 0; color: #F1F5F9; font-size: 14px; font-weight: 700;
                               font-family: monospace; letter-spacing: 0.5px;">{username}</td>
                  </tr>
                  <tr style="border-top: 1px solid rgba(255,255,255,0.06);">
                    <td style="padding: 8px 0; color: #4B5563; font-size: 13px;">Password</td>
                    <td style="padding: 8px 0; color: #F0A500; font-size: 14px; font-weight: 700;
                               font-family: monospace; letter-spacing: 0.5px;">{password}</td>
                  </tr>
                  <tr style="border-top: 1px solid rgba(255,255,255,0.06);">
                    <td style="padding: 8px 0; color: #4B5563; font-size: 13px;">Role</td>
                    <td style="padding: 8px 0; color: #E2E8F0; font-size: 13px; text-transform: capitalize;">{role}</td>
                  </tr>
                </table>
              </div>

              <div style="background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.2);
                          border-radius: 6px; padding: 12px 16px; margin-bottom: 24px;">
                <p style="margin: 0; color: #FCA5A5; font-size: 12px; line-height: 1.6;">
                  ⚠️ For security, please change your password immediately after first login via <strong>My Profile → Change Password</strong>.
                </p>
              </div>

              <p style="color: #1E293B; font-size: 11px; margin: 0;">
                © 2026 AML Monitor — Yerevan, Armenia
              </p>
            </div>
          </body>
        </html>
        """

        msg.attach(MIMEText(html, 'html'))

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls(context=context)
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(from_addr, to_email, msg.as_string())
        except Exception as e:
            print(f"\n[EMAIL - SMTP ERROR] Welcome email failed: {e}")
            print(f"[EMAIL - DEV FALLBACK] username: {username} | password: {password}\n")


    def send_demo_request(self, institution: str, requester_email: str):
        """
        Notify aml.monitoring.system@gmail.com that someone has requested a demo.
        Falls back to console print if SMTP is not configured.
        """
        ADMIN_EMAIL = "aml.monitoring.system@gmail.com"

        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            print(f"\n[DEMO REQUEST] Institution: {institution} | Email: {requester_email}\n")
            return

        from_addr = settings.SMTP_FROM or settings.SMTP_USER

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'🏦 New Demo Request — {institution}'
        msg['From']    = from_addr
        msg['To']      = ADMIN_EMAIL

        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; background: #081820; color: #EDF5F9; padding: 40px;">
            <div style="max-width: 520px; margin: 0 auto; background: #0F2533;
                        border-radius: 12px; padding: 32px; border: 1px solid #1A3D50;">
              <div style="margin-bottom: 24px;">
                <span style="font-size: 28px;">🛡️</span>
                <h2 style="margin: 4px 0 0; color: #EDF5F9;">AML Monitor</h2>
                <p style="margin: 0; color: #3D7A98; font-size: 12px;">New Demo Request Received</p>
              </div>

              <h3 style="color: #98C1D9; margin-bottom: 16px;">A new institution has requested a demo</h3>

              <table style="width:100%; border-collapse: collapse;">
                <tr>
                  <td style="padding: 10px 12px; background: #081820; border-radius: 6px 6px 0 0;
                             color: #7AAFC8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">
                    Institution / Bank
                  </td>
                </tr>
                <tr>
                  <td style="padding: 10px 12px; background: #0A1628; border-radius: 0 0 6px 6px;
                             color: #EDF5F9; font-size: 16px; font-weight: 700; margin-bottom: 12px;">
                    {institution}
                  </td>
                </tr>
              </table>
              <br/>
              <table style="width:100%; border-collapse: collapse;">
                <tr>
                  <td style="padding: 10px 12px; background: #081820; border-radius: 6px 6px 0 0;
                             color: #7AAFC8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">
                    Contact Email
                  </td>
                </tr>
                <tr>
                  <td style="padding: 10px 12px; background: #0A1628; border-radius: 0 0 6px 6px;
                             color: #98C1D9; font-size: 15px;">
                    <a href="mailto:{requester_email}" style="color: #98C1D9;">{requester_email}</a>
                  </td>
                </tr>
              </table>

              <p style="color: #3D7A98; font-size: 12px; margin-top: 28px;">
                Reply directly to <strong>{requester_email}</strong> to schedule the demo.
              </p>
            </div>
          </body>
        </html>
        """

        msg.attach(MIMEText(html, 'html'))

        # Confirmation email to the requester
        confirm_msg = MIMEMultipart('alternative')
        confirm_msg['Subject'] = 'Your Demo Request — AML Monitor'
        confirm_msg['From']    = from_addr
        confirm_msg['To']      = requester_email

        confirm_html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; background: #081820; color: #EDF5F9; padding: 40px;">
            <div style="max-width: 520px; margin: 0 auto; background: #0F2533;
                        border-radius: 12px; padding: 32px; border: 1px solid #1A3D50;">
              <div style="margin-bottom: 24px;">
                <span style="font-size: 28px;">🛡️</span>
                <h2 style="margin: 4px 0 0; color: #EDF5F9;">AML Monitor</h2>
                <p style="margin: 0; color: #3D7A98; font-size: 12px;">Transaction Monitoring System</p>
              </div>

              <h3 style="color: #98C1D9; margin-bottom: 12px;">Request Received!</h3>
              <p style="color: #B4D5E4; font-size: 14px; line-height: 1.7; margin-bottom: 20px;">
                Thank you for your interest in <strong style="color: #EDF5F9;">AML Monitor</strong>.
                We have received your demo request for <strong style="color: #EDF5F9;">{institution}</strong>
                and our compliance team will contact you shortly to schedule a personalised demo.
              </p>

              <div style="background: #081820; border-radius: 8px; padding: 16px 20px;
                          border: 1px solid #1A3D50; margin-bottom: 24px;">
                <p style="margin: 0 0 6px; color: #3D7A98; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Your request details</p>
                <p style="margin: 0; color: #EDF5F9; font-size: 14px;"><strong>Institution:</strong> {institution}</p>
                <p style="margin: 4px 0 0; color: #EDF5F9; font-size: 14px;"><strong>Email:</strong> {requester_email}</p>
              </div>

              <p style="color: #3D7A98; font-size: 12px; margin: 0;">
                If you did not submit this request, please ignore this email.<br/>
                © 2026 AML Monitor — Yerevan, Armenia
              </p>
            </div>
          </body>
        </html>
        """
        confirm_msg.attach(MIMEText(confirm_html, 'html'))

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls(context=context)
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(from_addr, ADMIN_EMAIL, msg.as_string())
                server.sendmail(from_addr, requester_email, confirm_msg.as_string())
        except Exception as e:
            print(f"\n[EMAIL - SMTP ERROR] Demo request email failed: {e}")
            print(f"[DEMO REQUEST] Institution: {institution} | Email: {requester_email}\n")


email_service = EmailService()
