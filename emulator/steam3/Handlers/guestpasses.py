import struct

from config import get_config
from steam3.ClientManager.client import Client
from steam3.messages.MSGClientSendGuestPass import MSGClientSendGuestPass
from steam3.messages.MSGClientAckGuestPass import MSGClientAckGuestPass
from steam3.messages.MSGClientRedeemGuestPass import MSGClientRedeemGuestPass
from steam3.Responses.guestpass_responses import build_SendAckGuestPassResponse, build_SendGuestPassResponse, build_RedeemGuestPassResponse
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMPacket
from steam3.Responses.general_responses import build_guest_pass_received_notification, build_guest_pass_granted_notification
from steam3.Managers.GuestPassManager import GuestPassManager


def _is_guestpass_disabled():
    """Check if the guestpass system is disabled in config."""
    config = get_config()
    return config.get('disable_guestpass_system', 'false').lower() == 'true'


def handle_SendGuestPass(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle sending a guest pass to another user"""
    # Check if guestpass system is disabled
    if _is_guestpass_disabled():
        cmserver_obj.log.debug("Guestpass system is disabled, returning OK for SendGuestPass")
        return [build_SendGuestPassResponse(client_obj, EResult.OK, 0)]

    request = packet.CMRequest
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Send Guest Pass Request")

    manager = GuestPassManager()
    giftID = 0
    emailAddr = b""
    accountID = 0xFFFFFFFF
    is_resend = False

    try:
        # Parse using the message class for better structure
        msg = MSGClientSendGuestPass(client_obj, request.data)

        giftID = msg.guest_pass_id
        accountID = msg.account_id
        emailAddr = msg.email_address.encode('utf-8') if msg.email_address else b""
        is_resend = getattr(msg, 'is_resend', False)

        cmserver_obj.log.info(f"Sending guest pass {giftID:016X} to "
                              f"{'email: ' + msg.email_address if accountID == 0xFFFFFFFF else 'account: ' + str(accountID)}")

        # Use GuestPassManager to send the pass
        recipient_account = accountID if accountID != 0xFFFFFFFF else None
        recipient_email = msg.email_address if accountID == 0xFFFFFFFF else None

        success, message = manager.send_pass(
            pass_id=giftID,
            sender_account_id=client_obj.steamID,
            recipient_account_id=recipient_account,
            recipient_email=recipient_email,
            is_resend=is_resend
        )

        if not success:
            cmserver_obj.log.error(f"Failed to send guest pass: {message}")
            # Determine appropriate error code
            if "not found" in message.lower():
                return [build_SendGuestPassResponse(client_obj, EResult.InvalidParam, giftID)]
            elif "not owned" in message.lower():
                return [build_SendGuestPassResponse(client_obj, EResult.AccessDenied, giftID)]
            elif "already sent" in message.lower():
                return [build_SendGuestPassResponse(client_obj, EResult.DuplicateRequest, giftID)]
            elif "expired" in message.lower():
                return [build_SendGuestPassResponse(client_obj, EResult.Expired, giftID)]
            else:
                return [build_SendGuestPassResponse(client_obj, EResult.Fail, giftID)]

        cmserver_obj.log.info(f"Guest pass {giftID} successfully sent")

        # Send email notification if sending by email
        if recipient_email:
            _send_guest_pass_email(cmserver_obj, client_obj, giftID, recipient_email)

    except Exception as e:
        cmserver_obj.log.error(f"Failed to parse SendGuestPass: {e}")
        # Fallback to old parsing method
        try:
            unpack_fmt = "<QBI"
            giftID, is_resend_flag, accountID = struct.unpack_from(unpack_fmt, request.data, 0)
            emailAddr = request.data[struct.calcsize(unpack_fmt):-1]
        except Exception as parse_error:
            cmserver_obj.log.error(f"Fallback parsing also failed: {parse_error}")
            return [build_SendGuestPassResponse(client_obj, EResult.InvalidParam, 0)]

    responses = [build_SendGuestPassResponse(client_obj, EResult.OK, giftID)]

    # Send SystemIM notification to the sender about guest pass being granted
    try:
        recipient_display = emailAddr.decode('utf-8', errors='ignore') if emailAddr else f"User {accountID}"
        notification = build_guest_pass_granted_notification(client_obj, recipient_display)
        responses.append(notification)
        cmserver_obj.log.debug(f"Sending guest pass granted notification to sender")
    except Exception as e:
        cmserver_obj.log.error(f"Error sending guest pass granted notification: {e}")

    return responses


def _send_guest_pass_email(cmserver_obj, client_obj: Client, guest_pass_id: int, recipient_email: str):
    """Send email notification for a guest pass."""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from config import get_config

        config = get_config()
        if not config.get('smtp_enabled', False):
            return

        smtp_host = config.get('smtp_host', 'localhost')
        smtp_port = config.get('smtp_port', 587)
        smtp_user = config.get('smtp_user', '')
        smtp_pass = config.get('smtp_password', '')

        msg_email = MIMEText(f"""You have received a Steam guest pass!

From: {client_obj.username}
Guest Pass ID: {guest_pass_id}

Please log into Steam to redeem your guest pass.""")
        msg_email['Subject'] = 'Steam Guest Pass'
        msg_email['From'] = smtp_user
        msg_email['To'] = recipient_email

        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg_email)
        server.quit()

        cmserver_obj.log.info(f"Guest pass email sent to {recipient_email}")
    except Exception as e:
        cmserver_obj.log.error(f"Failed to send guest pass email: {e}")


def handle_AckGuestPass(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle acknowledgment of a guest pass"""
    # Check if guestpass system is disabled
    if _is_guestpass_disabled():
        cmserver_obj.log.debug("Guestpass system is disabled, returning OK for AckGuestPass")
        return [build_SendAckGuestPassResponse(client_obj, EResult.OK, 0)]

    request = packet.CMRequest
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Guest Pass Acknowledgment")

    manager = GuestPassManager()
    guestpassKey = 0

    try:
        # Parse using the message class
        msg = MSGClientAckGuestPass(client_obj, request.data)
        guestpassKey = msg.guest_pass_id

        cmserver_obj.log.info(f"Acknowledging guest pass: 0x{guestpassKey:016X}")

    except Exception as e:
        cmserver_obj.log.error(f"Failed to parse AckGuestPass: {e}")
        # Fallback to old parsing method
        try:
            unpack_fmt = "<Q"
            guestpassKey = struct.unpack_from(unpack_fmt, request.data, 0)[0]
        except Exception:
            return [build_SendAckGuestPassResponse(client_obj, EResult.InvalidParam, 0)]

    # Use GuestPassManager to acknowledge the pass
    success, message = manager.acknowledge_pass(guestpassKey, client_obj.steamID)

    if not success:
        cmserver_obj.log.warning(f"Guest pass acknowledgment issue: {message}")
        # Still return OK as acknowledgment is not critical
        # The pass might be sent to an email that's associated with this account

    cmserver_obj.log.info(f"Guest pass {guestpassKey} acknowledged")
    return [build_SendAckGuestPassResponse(client_obj, EResult.OK, guestpassKey)]


def handle_RedeemGuestPass(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle redemption of a guest pass"""
    # Check if guestpass system is disabled
    if _is_guestpass_disabled():
        cmserver_obj.log.debug("Guestpass system is disabled, returning OK for RedeemGuestPass")
        return [build_RedeemGuestPassResponse(client_obj, EResult.OK, 0, 0)]

    request = packet.CMRequest
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Guest Pass Redemption Request")

    manager = GuestPassManager()
    guestpassID = 0

    try:
        # Parse using the message class
        msg = MSGClientRedeemGuestPass(client_obj, request.data)
        guestpassID = msg.guest_pass_id
    except Exception as e:
        cmserver_obj.log.error(f"Failed to parse RedeemGuestPass: {e}")
        # Fallback to old parsing method
        try:
            unpack_fmt = "<Q"
            guestpassID = struct.unpack_from(unpack_fmt, request.data, 0)[0]
        except Exception:
            return [build_RedeemGuestPassResponse(client_obj, EResult.InvalidParam, 0, 0)]

    cmserver_obj.log.info(f"Redeeming guest pass: 0x{guestpassID:016X}")

    # Use GuestPassManager to redeem the pass
    success, packageID, message = manager.redeem_pass(guestpassID, client_obj.steamID)

    if not success:
        cmserver_obj.log.error(f"Failed to redeem guest pass: {message}")
        # Determine appropriate error code
        if "not found" in message.lower():
            return [build_RedeemGuestPassResponse(client_obj, EResult.InvalidParam, guestpassID, 0)]
        elif "not the recipient" in message.lower():
            return [build_RedeemGuestPassResponse(client_obj, EResult.AccessDenied, guestpassID, 0)]
        elif "already redeemed" in message.lower():
            return [build_RedeemGuestPassResponse(client_obj, EResult.DuplicateRequest, guestpassID, packageID)]
        elif "expired" in message.lower():
            return [build_RedeemGuestPassResponse(client_obj, EResult.Expired, guestpassID, 0)]
        else:
            return [build_RedeemGuestPassResponse(client_obj, EResult.Fail, guestpassID, 0)]

    cmserver_obj.log.info(f"Guest pass {guestpassID} redeemed for package {packageID}")

    responses = [build_RedeemGuestPassResponse(client_obj, EResult.OK, guestpassID, packageID)]

    # Send SystemIM notification about guest pass redemption
    try:
        notification = build_guest_pass_received_notification(client_obj, "Steam System")
        responses.append(notification)
        cmserver_obj.log.debug(f"Sending guest pass received notification")
    except Exception as e:
        cmserver_obj.log.error(f"Error sending guest pass received notification: {e}")

    return responses