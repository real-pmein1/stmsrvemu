"""Credit card block rules for the Steam2 subscribe path.

A blocked card no longer just aborts the purchase: it makes the auth server hand
the client a subscription record whose eSubscriptionStatus is one of the values
that SteamUI.dll turns into a receipt dialog.

SteamUI.dll picks steam/cached/Receipt_*.res purely from the
TSteamSubscriptionReceipt it reads back through SteamGetSubscriptionReceipt
(eStatus, ePreviousStatus, eReceiptInfoType), so the status we store in
AccountSubscriptionsRecord is what decides which dialog the user sees.
"""

# ESteamSubscriptionStatus (SteamCommon.h)
STATUS_OK = 0
STATUS_PENDING = 1
STATUS_PREORDER = 2
STATUS_PREPURCHASE_TRANSFERRED = 3
STATUS_PREPURCHASE_INVALID = 4
STATUS_PREPURCHASE_REJECTED = 5
STATUS_PREPURCHASE_REVOKED = 6
STATUS_PAYMENTCARD_DECLINED = 7
STATUS_CANCELLED_BY_USER = 8
STATUS_CANCELLED_BY_VENDOR = 9
STATUS_PAYMENTCARD_USELIMIT = 10
STATUS_PAYMENTCARD_ALERT = 11
STATUS_FAILED = 12
STATUS_PAYMENTCARD_AVS_FAILURE = 13
STATUS_PAYMENTCARD_INSUFFICIENT_FUNDS = 14
STATUS_RESTRICTED_COUNTRY = 15

# Accepted names in creditcard_blacklist.txt, all lowercased for lookup.
# Short aliases are the ones a config file is likely to use.
STATUS_NAMES = {
        'ok':                            STATUS_OK,
        'pending':                       STATUS_PENDING,
        'preorder':                      STATUS_PREORDER,
        'prepurchasetransferred':        STATUS_PREPURCHASE_TRANSFERRED,
        'transferred':                   STATUS_PREPURCHASE_TRANSFERRED,
        'prepurchaseinvalid':            STATUS_PREPURCHASE_INVALID,
        'invalidkey':                    STATUS_PREPURCHASE_INVALID,
        'prepurchaserejected':           STATUS_PREPURCHASE_REJECTED,
        'rejected':                      STATUS_PREPURCHASE_REJECTED,
        'prepurchaserevoked':            STATUS_PREPURCHASE_REVOKED,
        'revoked':                       STATUS_PREPURCHASE_REVOKED,
        'hopped':                        STATUS_PREPURCHASE_REVOKED,
        'paymentcarddeclined':           STATUS_PAYMENTCARD_DECLINED,
        'declined':                      STATUS_PAYMENTCARD_DECLINED,
        'cancelledbyuser':               STATUS_CANCELLED_BY_USER,
        'cancelledbyvendor':             STATUS_CANCELLED_BY_VENDOR,
        'cancelled':                     STATUS_CANCELLED_BY_VENDOR,
        'paymentcarduselimit':           STATUS_PAYMENTCARD_USELIMIT,
        'uselimit':                      STATUS_PAYMENTCARD_USELIMIT,
        'paymentcardalert':              STATUS_PAYMENTCARD_ALERT,
        'alert':                         STATUS_PAYMENTCARD_ALERT,
        'fraud':                         STATUS_PAYMENTCARD_ALERT,
        'failed':                        STATUS_FAILED,
        'paymentcardavsfailure':         STATUS_PAYMENTCARD_AVS_FAILURE,
        'avsfailure':                    STATUS_PAYMENTCARD_AVS_FAILURE,
        'avs':                           STATUS_PAYMENTCARD_AVS_FAILURE,
        'paymentcardinsufficientfunds':  STATUS_PAYMENTCARD_INSUFFICIENT_FUNDS,
        'insufficientfunds':             STATUS_PAYMENTCARD_INSUFFICIENT_FUNDS,
        'restrictedcountry':             STATUS_RESTRICTED_COUNTRY,
}

# Statuses SteamUI.dll maps onto a dedicated receipt dialog. ePreviousStatus
# decides between the two entries where a tuple is listed: index 0 is used when
# the subscription was a preorder (ePreviousStatus == STATUS_PREORDER), index 1
# otherwise.
STATUS_RECEIPT_DIALOGS = {
        STATUS_PREORDER:                       ('Receipt_CC_Preorder.res',),
        STATUS_PREPURCHASE_TRANSFERRED:        ('Receipt_CDKey_Success_Transferred.res',),
        STATUS_PREPURCHASE_INVALID:            ('Receipt_CDKey_InvalidKey.res',),
        STATUS_PREPURCHASE_REJECTED:           ('Receipt_CDKey_Rejected.res',),
        STATUS_PREPURCHASE_REVOKED:            ('Receipt_CDKey_Hopped.res',),
        STATUS_PAYMENTCARD_DECLINED:           ('Receipt_CC_Denied_FromPreorder.res', 'Receipt_CC_Declined.res'),
        STATUS_CANCELLED_BY_USER:              ('Receipt_PreorderCancelled.res', 'Receipt_CDKey_Cancelled.res'),
        STATUS_CANCELLED_BY_VENDOR:            ('Receipt_PreorderCancelled.res', 'Receipt_CDKey_Cancelled.res'),
        STATUS_PAYMENTCARD_USELIMIT:           ('Receipt_CC_UseLimit.res',),
        STATUS_PAYMENTCARD_ALERT:              ('Receipt_CC_Alert.res',),
        STATUS_PAYMENTCARD_AVS_FAILURE:        ('Receipt_CC_Declined_AVSFailure.res',),
        STATUS_PAYMENTCARD_INSUFFICIENT_FUNDS: ('Receipt_CC_Declined_InsufficientFunds.res',),
        STATUS_RESTRICTED_COUNTRY:             ('Receipt_Restricted_Country.res',),
}

# What a rule without an explicit status resolves to. PaymentCardDeclined is the
# plain "your credit card was declined, purchase not completed" dialog
# (Receipt_CC_Declined.res). Rules that want the fraud dialogs have to ask for
# UseLimit or Alert explicitly.
DEFAULT_BLOCK_STATUS = STATUS_PAYMENTCARD_DECLINED

# ePreviousStatus written alongside a blocked status. A card transaction always
# passes through Pending before the processor answers, and it must not be
# STATUS_PREORDER or the client swaps in the preorder variant of the dialog.
BLOCKED_PREVIOUS_STATUS = STATUS_PENDING


def parse_status(text, default = DEFAULT_BLOCK_STATUS):
    """Accept either a numeric status or one of the names in STATUS_NAMES."""
    if text is None:
        return default

    text = text.strip()
    if not text:
        return default

    if text.lstrip('-').isdigit():
        value = int(text)
    else:
        value = STATUS_NAMES.get(text.replace(' ', '').replace('_', '').lower())
        if value is None:
            return None

    return value if value in STATUS_RECEIPT_DIALOGS else None


def get_receipt_dialog(status, previous_status = BLOCKED_PREVIOUS_STATUS):
    """Which Receipt_*.res SteamUI will load for a status. Debug aid only."""
    dialogs = STATUS_RECEIPT_DIALOGS.get(status)
    if not dialogs:
        return 'Receipt_Server_Failure.res'
    if len(dialogs) == 1:
        return dialogs[0]
    return dialogs[0] if previous_status == STATUS_PREORDER else dialogs[1]


def get_block_status(card_number, block_rules):
    """Return the eSubscriptionStatus to report for a card, or None if allowed."""
    if not card_number:
        return None

    card_numbers = block_rules.get('card_numbers', {})
    if card_number in card_numbers:
        return card_numbers[card_number]

    for group, status in block_rules.get('groups', {}).items():
        if card_number.startswith(group):
            return status

    card_type = get_card_type(card_number)
    card_types = block_rules.get('card_types', {})
    if card_type in card_types:
        return card_types[card_type]

    return None


def is_card_blocked(card_number, block_rules):
    return get_block_status(card_number, block_rules) is not None


def get_card_type(card_number):
    # Dummy implementation - should be replaced with actual logic
    if card_number.startswith('4'):
        return 'Visa'
    elif card_number.startswith('5'):
        return 'MasterCard'
    # Add other card types as needed
    return 'Unknown'


def load_block_rules(file_path):
    """Parse creditcard_blacklist.txt into {kind: {value: status}}.

    Each rule may carry an optional status suffix:
        CARD:4111111111111111=UseLimit
        GROUP:5500=insufficientfunds
        TYPE:Visa=7
    Rules without a suffix fall back to DEFAULT_BLOCK_STATUS.
    """
    block_rules = {
            'card_numbers':{},
            'groups':      {},
            'card_types':  {}
    }

    kinds = {
            'CARD':  'card_numbers',
            'GROUP': 'groups',
            'TYPE':  'card_types'
    }

    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
    except FileNotFoundError:
        return block_rules

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        prefix, _, remainder = line.partition(':')
        target = kinds.get(prefix.strip().upper())
        if not target:
            continue

        value, _, status_text = remainder.partition('=')
        value = value.strip()
        if not value:
            continue

        status = parse_status(status_text if status_text else None)
        if status is None:
            # Unknown or dialog-less status; treat the rule as a plain block.
            status = DEFAULT_BLOCK_STATUS

        block_rules[target][value] = status

    return block_rules
