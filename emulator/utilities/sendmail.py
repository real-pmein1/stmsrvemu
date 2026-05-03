import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import utils
from config import get_config as read_config

config = read_config()


def send_email_via_smtp(msg):
    smtp_server = config['smtp_serverip']
    smtp_port = config['smtp_serverport']
    smtp_username = config['smtp_username']
    smtp_password = config['smtp_password']
    smtp_security = config['smtp_security']
    reply_to_email = config['support_email'].lower()

    try:
        # Create an SMTP connection
        if smtp_security.lower() == "ssl":
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()  # Use TLS encryption

        # Login to the SMTP server (if authentication is required)
        if smtp_username and smtp_password:
            server.login(smtp_username, smtp_password)

        # Add default Reply-To header if not already set
        if 'Reply-To' not in msg:
            msg['Reply-To'] = reply_to_email

        # Send the email
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        server.quit()
        print("Email sent successfully.")
        return True
    except Exception as e:
        print("Error sending email:", str(e))
        return False


def send_templated_email(to_email, subject, template_name, **kwargs):
    """Send an email using the provided template."""
    body = load_email_template(template_name, **kwargs)
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email
    part = MIMEText(body, 'html')
    msg.attach(part)
    return send_email_via_smtp(msg)


def load_email_template(template_name, **kwargs):
    template_path = os.path.join('files', 'email_tpl', template_name)
    with open(template_path, 'r') as file:
        template = file.read()

    kwargs['support_email'] = config['support_email']
    kwargs['network_name'] = config['network_name']
    kwargs['network_url'] = config['http_ip']
    kwargs['logo_url'] = config['network_logo']

    if config['email_location_support'].lower() == "true":
        country, region_name = utils.get_location(kwargs['ipaddress'])
        kwargs['ip_location_msg'] = f" (Location: {country}, {region_name})"
        print(f'Country: {country}, Region: {region_name}')
    else:
        kwargs['ip_location_msg'] = ""

    return template.format(**kwargs)


def send_username_email(to_email, username, ipaddress):
    subject = "Steam account - Query account by email address" #f"{config['network_name']}: Username Retrieval"
    body = load_email_template('username_retrieval.tpl', username = username, ipaddress = ipaddress[0])

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    # Attach the HTML version of the body
    part = MIMEText(body, 'html')
    msg.attach(part)

    send_email_via_smtp(msg)


def send_reset_password_email(to_email, verification_code, question, ipaddress, username):
    subject = "Steam account - Forgotten password" #f"{config['network_name']}: Password Reset Request"
    body = load_email_template('password_reset_request.tpl', verification_code = verification_code, question = question, ipaddress = ipaddress[0], username = username)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    # Attach the HTML version of the body
    part = MIMEText(body, 'html')
    msg.attach(part)

    send_email_via_smtp(msg)


def send_verification_email(to_email, verification_token, ipaddress, username):
    subject = f"{config['network_name']}: Account Verification"
    return send_templated_email(
        to_email,
        subject,
        'account_verification.tpl',
        verification_code=verification_token,
        ipaddress=ipaddress[0],
        username=username,
    )


def send_new_user_email(to_email, ipaddress, username, validationcode):
    subject = f"Welcome to {config['network_name']}!"
    return send_templated_email(
        to_email,
        subject,
        'new_user_welcome.tpl',
        ipaddress=ipaddress[0],
        username=username,
        validation=validationcode,
    )


def send_password_changed_email(to_email, ipaddress, username):
    subject = f"{config['network_name']}: Password Change Notice"
    body = load_email_template('password_changed_notice.tpl', ipaddress = ipaddress[0], username = username)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    # Attach the HTML version of the body
    part = MIMEText(body, 'html')
    msg.attach(part)

    send_email_via_smtp(msg)

def send_attempted_pw_change_email(to_email, ipaddress, username):
    subject = f"{config['network_name']}: Password Change Attempt Notice"
    body = load_email_template('attempted_password_change.tpl', ipaddress = ipaddress[0], username = username)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    # Attach the HTML version of the body
    part = MIMEText(body, 'html')
    msg.attach(part)

    send_email_via_smtp(msg)

def send_question_changed_confirmation(to_email, ipaddress, username):
    subject = f"{config['network_name']}: Security Question Update Confirmation"
    body = load_email_template('question_changed_notice.tpl', ipaddress = ipaddress[0], username = username)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    # Attach the HTML version of the body
    part = MIMEText(body, 'html')
    msg.attach(part)

    send_email_via_smtp(msg)

def send_email_changed_email(to_email, ipaddress, username):
    subject = f"{config['network_name']}: Email Address Update Confirmation"
    body = load_email_template('email_changed_notice.tpl', ipaddress = ipaddress[0], username = username)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    # Attach the HTML version of the body
    part = MIMEText(body, 'html')
    msg.attach(part)

    send_email_via_smtp(msg)


def send_friends_invite_email(to_email, ipaddress, username):
    subject = f"{config['network_name']}: {username} Send You A Steam Friends Invitation!"
    body = load_email_template('invite_friends_by_email.tpl', ipaddress = ipaddress[0], username = username, email = to_email)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    # Attach the HTML version of the body
    part = MIMEText(body, 'html')
    msg.attach(part)

    send_email_via_smtp(msg)

def send_validation_code_email(to_email, verification_token, ipaddress, username):
    subject = f"{config['network_name']}: Email Address Validation"
    body = load_email_template('email_validation.tpl', verification_code = verification_token, ipaddress = ipaddress[0], username = username)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    # Attach the HTML version of the body
    part = MIMEText(body, 'html')
    msg.attach(part)

    send_email_via_smtp(msg)


def send_purchase_receipt_email(to_email, username, items, subtotal, tax, total, currency,
                                 payment_method, card_last_four, confirmation_number, date_confirmed):
    """Send a purchase receipt email.

    Args:
        to_email: Recipient email address
        username: Steam username
        items: List of dicts with 'name' and 'price' keys for each item purchased
        subtotal: Subtotal amount as string
        tax: Tax amount as string
        total: Total amount as string
        currency: Currency code (e.g., 'USD')
        payment_method: Payment method name (e.g., 'Visa', 'MasterCard')
        card_last_four: Last 4 digits of the card
        confirmation_number: Transaction confirmation number
        date_confirmed: Date/time of confirmation as string
    """
    subject = "Thank you for your purchase"

    # Build line items HTML
    line_items_html = ""
    for item in items:
        line_items_html += f'<tr><td width="200"><div align="right"><b>{item["name"]}&nbsp;&nbsp;</b></div></td><td width="202">{item["price"]} {currency}</td></tr>\n'

    body = load_email_template(
        'purchase_receipt.tpl',
        username=username,
        line_items=line_items_html,
        subtotal=subtotal,
        tax=tax,
        total=total,
        currency=currency,
        payment_method=payment_method,
        card_last_four=card_last_four,
        confirmation_number=confirmation_number,
        date_confirmed=date_confirmed,
        ipaddress="0.0.0.0"
    )

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    part = MIMEText(body, 'html')
    msg.attach(part)

    return send_email_via_smtp(msg)


def send_gift_purchase_receipt_email(to_email, username, items, subtotal, tax, total, currency,
                                      payment_method, card_last_four, confirmation_number, date_confirmed):
    """Send a gift purchase receipt email.

    Args:
        to_email: Recipient email address
        username: Steam username
        items: List of dicts with 'name' and 'price' keys for each gift item purchased
        subtotal: Subtotal amount as string
        tax: Tax amount as string
        total: Total amount as string
        currency: Currency code (e.g., 'USD')
        payment_method: Payment method name (e.g., 'Visa', 'MasterCard')
        card_last_four: Last 4 digits of the card
        confirmation_number: Transaction confirmation number
        date_confirmed: Date/time of confirmation as string
    """
    subject = "Thank you for your gift purchase"

    # Build line items HTML
    line_items_html = ""
    for item in items:
        line_items_html += f'<tr><td width="200"><div align="right"><b>{item["name"]}&nbsp;&nbsp;</b></div></td><td width="202">{item["price"]} {currency}</td></tr>\n'

    body = load_email_template(
        'gift_purchase_receipt.tpl',
        username=username,
        line_items=line_items_html,
        subtotal=subtotal,
        tax=tax,
        total=total,
        currency=currency,
        payment_method=payment_method,
        card_last_four=card_last_four,
        confirmation_number=confirmation_number,
        date_confirmed=date_confirmed,
        ipaddress="0.0.0.0"
    )

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    part = MIMEText(body, 'html')
    msg.attach(part)

    return send_email_via_smtp(msg)


def send_new_computer_access_email(to_email, username, access_code):
    """Send a SteamGuard new computer access code email.

    Args:
        to_email: Recipient email address
        username: Steam username
        access_code: The SteamGuard access code
    """
    subject = "Your Steam account: Access from new computer"

    body = load_email_template(
        'new_computer_access.tpl',
        username=username,
        access_code=access_code,
        ipaddress="0.0.0.0"
    )

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    part = MIMEText(body, 'html')
    msg.attach(part)

    return send_email_via_smtp(msg)


def send_wishlist_sale_email(to_email, username, wishlist_items, unsubscribe_url=""):
    """Send a wishlist sale notification email.

    Args:
        to_email: Recipient email address
        username: Steam username
        wishlist_items: List of dicts with game sale info:
            - 'name': Game name
            - 'app_id': Steam app ID
            - 'header_image': URL to game header image
            - 'discount_percent': Discount percentage (e.g., '80')
            - 'original_price': Original price string
            - 'sale_price': Sale price string
            - 'sale_end_date': Optional sale end date string
        unsubscribe_url: URL to unsubscribe from wishlist emails
    """
    subject = "A game on your wishlist is on sale!"

    # Load item template
    item_template_path = os.path.join('files', 'email_tpl', 'wishlist_sale_item.tpl')
    with open(item_template_path, 'r') as file:
        item_template = file.read()

    # Build wishlist items HTML from template
    wishlist_items_html = ""
    for item in wishlist_items:
        sale_end_html = ""
        if item.get('sale_end_date'):
            sale_end_html = f'<p style="color: #7CB8E4; padding: 0; margin: 0; font-size: 12px;">Offer ends {item["sale_end_date"]}</p>'

        wishlist_items_html += item_template.format(
            network_url=config['http_ip'],
            app_id=item['app_id'],
            header_image=item['header_image'],
            name=item['name'],
            discount_percent=item['discount_percent'],
            original_price=item['original_price'],
            sale_price=item['sale_price'],
            sale_end_html=sale_end_html
        )

    body = load_email_template(
        'wishlist_sale.tpl',
        username=username,
        wishlist_items=wishlist_items_html,
        unsubscribe_url=unsubscribe_url,
        ipaddress="0.0.0.0"
    )

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    part = MIMEText(body, 'html')
    msg.attach(part)

    return send_email_via_smtp(msg)


def send_gift_received_email(to_email, recipient_email, sender_username, sender_email, sender_avatar_url,
                              game_name, game_header_image, gift_code, gift_recipient_name="",
                              gift_message="", gift_sentiment="", gift_signature=""):
    """Send a gift received notification email.

    Args:
        to_email: Recipient email address
        recipient_email: Recipient email (for redeem URL)
        sender_username: Gift sender's username
        sender_email: Gift sender's email address
        sender_avatar_url: URL to sender's avatar image
        game_name: Name of the gifted game
        game_header_image: URL to game header image
        gift_code: Gift redemption code
        gift_recipient_name: Name greeting in gift message (e.g., "Dear Friend")
        gift_message: Personal message from sender
        gift_sentiment: Closing sentiment (e.g., "Best wishes")
        gift_signature: Sender's signature name
    """
    import urllib.parse

    subject = f"You've received a gift copy of the game {game_name} on Steam"

    encoded_email = urllib.parse.quote(recipient_email)
    redeem_url = f"https://store.steampowered.com/account/ackgift/{gift_code}?redeemer={encoded_email}"
    redeem_url_client = f"https://store.steampowered.com/account/ackgift/{gift_code}?client=1&redeemer={encoded_email}"

    body = load_email_template(
        'gift_received.tpl',
        sender_username=sender_username,
        sender_email=sender_email,
        sender_avatar_url=sender_avatar_url,
        game_name=game_name,
        game_header_image=game_header_image,
        redeem_url=redeem_url,
        redeem_url_client=redeem_url_client,
        gift_recipient_name=gift_recipient_name if gift_recipient_name else "Dear Friend",
        gift_message=gift_message if gift_message else "",
        gift_sentiment=gift_sentiment if gift_sentiment else "Enjoy!",
        gift_signature=gift_signature if gift_signature else sender_username,
        ipaddress="0.0.0.0"
    )

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    part = MIMEText(body, 'html')
    msg.attach(part)

    return send_email_via_smtp(msg)


def send_forgotten_password_email(to_email, username, verification_code):
    """Send a forgotten password email with verification code (Steam format).

    This version matches the original Steam email format without the secret question field.

    Args:
        to_email: Recipient email address
        username: Steam username
        verification_code: The password reset verification code
    """
    subject = "Steam account - Forgotten password"

    body = load_email_template(
        'forgotten_password.tpl',
        username=username,
        verification_code=verification_code,
        ipaddress="0.0.0.0"
    )

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    part = MIMEText(body, 'html')
    msg.attach(part)

    return send_email_via_smtp(msg)


def send_query_account_by_email(to_email, username):
    """Send an account query email showing the username associated with an email (Steam format).

    This version matches the original Steam email format exactly.

    Args:
        to_email: Recipient email address
        username: Steam username to display
    """
    subject = "Steam account - Query account by email address"

    body = load_email_template(
        'query_account_by_email.tpl',
        username=username,
        ipaddress="0.0.0.0"
    )

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{config['network_name']} <{config['support_email']}>"
    msg['To'] = to_email

    part = MIMEText(body, 'html')
    msg.attach(part)

    return send_email_via_smtp(msg)


if __name__ == "__main__":
    send_new_user_email(sys.argv[1], sys.argv[2], sys.argv[3], 0)
