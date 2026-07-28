# Credit Card Blacklist

Blocks credit cards from completing a Steam2 purchase, and controls **which
error dialog the client shows** when a blocked card is used.

Config file: `files/configs/creditcard_blacklist.txt`
Code: `utilities/auth_cc_blocker.py`, used by `servers/authserver.py` (Subscribe,
command `0x05`) and `utilities/database/authdb.py`.

---

## How it works

A Steam2 client does not learn about a failed purchase from the response byte of
the Subscribe command. It learns about it from the **subscription record inside
the account blob**. After subscribing, the client calls
`SteamGetSubscriptionReceipt` and `SteamUI.dll` picks a dialog
(`steam/cached/Receipt_*.res`) purely from the `eSubscriptionStatus` it reads
back.

So a blocked card is not handled by refusing the purchase. Instead the server:

1. Writes the subscription record anyway, with `eSubscriptionStatus` set to the
   failure status the rule asked for, `eStatusChangeFlag = 1` (there is a new
   receipt waiting) and `ePreviousSubscriptionState = 1` (Pending).
2. Writes the payment-card record so the dialog can render the card type, last
   four digits, cardholder name and billing zip.
3. Replies with the **success** byte `\x00` plus the account blob. The decline
   lives in the blob, not in the response code.

Replying with an error byte instead makes the client give up before it fetches a
receipt, and it falls back to the generic `#Steam_SubscribeFailedInfo` message
box ("your credit card information has been rejected") — which is what the old
behaviour did.

The rules file is re-read on every purchase, so edits take effect without
restarting the server.

---

## Rule syntax

One rule per line. Lines starting with `#` are comments, blank lines are
ignored.

```
CARD:<full card number>
GROUP:<leading digits of the card number>
TYPE:<card brand>
```

Any rule may carry an optional status suffix that selects the dialog:

```
CARD:5500000000000004=UseLimit
GROUP:1234=15
TYPE:Visa=insufficient_funds
```

* **No suffix** → `Declined` (7), the normal "your purchase was not completed,
  your credit card was declined" error.
* Status names are case-insensitive and ignore spaces and underscores, so
  `AVSFailure`, `avsfailure` and `AVS_Failure` are the same.
* The numeric value can be used instead of the name.
* An unrecognized name, or a status that has no dialog, falls back to
  `Declined` rather than failing the file load.

Matching order is: exact card number, then group prefix, then card brand. The
first match wins.

### Card brands

`TYPE:` matches the brand derived by `get_card_type()`. That helper is currently
a stub that only recognizes `Visa` (numbers starting with `4`) and `MasterCard`
(starting with `5`); anything else is `Unknown`. Extend `get_card_type()` if you
need `Amex`, `Discover` and the rest.

---

## Statuses

These are `ESteamSubscriptionStatus` values (`SteamCommon.h` in the Steam2 SDK).
Only the values that map to a dedicated receipt dialog are accepted.

| Name | Value | Dialog | What the user sees |
|---|---|---|---|
| `Preorder` | 2 | `Receipt_CC_Preorder` | preorder placed |
| `Transferred` | 3 | `Receipt_CDKey_Success_Transferred` | key transferred to this account |
| `InvalidKey` | 4 | `Receipt_CDKey_InvalidKey` | invalid CD key |
| `Rejected` | 5 | `Receipt_CDKey_Rejected` | key rejected |
| `Hopped` / `Revoked` | 6 | `Receipt_CDKey_Hopped` | key moved to another account |
| `Declined` | 7 | `Receipt_CC_Declined` | **default** — card declined by the bank |
| `CancelledByUser` | 8 | `Receipt_CDKey_Cancelled` | cancelled |
| `Cancelled` | 9 | `Receipt_CDKey_Cancelled` | cancelled by the vendor |
| `UseLimit` | 10 | `Receipt_CC_UseLimit` | card used too many times in Steam (fraud policy) |
| `Alert` / `fraud` | 11 | `Receipt_CC_Alert` | bank flagged the card as potentially fraudulent |
| `AVSFailure` / `AVS` | 13 | `Receipt_CC_Declined_AVSFailure` | billing address did not verify |
| `InsufficientFunds` | 14 | `Receipt_CC_Declined_InsufficientFunds` | not enough funds |
| `RestrictedCountry` | 15 | `Receipt_Restricted_Country` | not available in this country |

Statuses 0 (OK), 1 (Pending) and 12 (Failed) are deliberately not accepted — the
client renders them as success or as a generic server failure.

If `ePreviousSubscriptionState` is `2` (Preorder), the client swaps in the
preorder variants (`Receipt_CC_Denied_FromPreorder`,
`Receipt_PreorderCancelled`). The blacklist always writes `1` (Pending) so the
normal variants are used.

---

## Example

```
# Known-bad test cards
CARD:4111111111111111
CARD:5500000000000004=UseLimit
CARD:1234567890123456=Alert

# Whole BIN ranges
GROUP:4012
GROUP:9999=RestrictedCountry
GROUP:3782=14

# Whole brands
TYPE:MasterCard=AVSFailure
```

With that file:

| Card | Result |
|---|---|
| `4111111111111111` | `Receipt_CC_Declined` |
| `5500000000000004` | `Receipt_CC_UseLimit` |
| `1234567890123456` | `Receipt_CC_Alert` |
| `4012888888881881` | `Receipt_CC_Declined` (GROUP match) |
| `9999000000000000` | `Receipt_Restricted_Country` |
| `3782822463100005` | `Receipt_CC_Declined_InsufficientFunds` |
| `5105105105105100` | `Receipt_CC_Declined_AVSFailure` (TYPE match) |
| `4999999999999999` | not blocked, purchase completes |

The server logs the decision for each blocked purchase, including the resolved
status and the `.res` file the client should load.

---

## API

`utilities/auth_cc_blocker.py`

| Function | Purpose |
|---|---|
| `load_block_rules(path)` | Parse the file into `{'card_numbers': {...}, 'groups': {...}, 'card_types': {...}}`, each mapping a value to a status int. Missing file returns empty rules. |
| `get_block_status(card_number, rules)` | The status to report for a card, or `None` if the card is allowed. |
| `is_card_blocked(card_number, rules)` | Boolean wrapper around `get_block_status`. |
| `get_receipt_dialog(status, previous_status)` | The `Receipt_*.res` the client will load for a status. Logging/debug aid. |
| `parse_status(text, default)` | Resolve a name or number to a status, or `None` if it has no dialog. |
| `get_card_type(card_number)` | Brand used by `TYPE:` rules. |

`utilities/database/authdb.py`

`insert_subscription(..., forced_status=None, forced_previous_status=None)` —
when `forced_status` is set, the subscription is written with that status,
`StatusChangeFlag = 1`, and `ePreviousSubscriptionState` defaulting to Pending.
Retrying the same subscription id updates the existing rows instead of bailing
out or duplicating them.

---

## Limitations

* Steam2 purchases only. The Steam3 purchase path (`PurchaseResponse_t`) has no
  cases for `UseLimit` or `Alert` in the SteamUI builds checked, so a package
  flagged `OptionalIsSteam3Subscription` in the CDR cannot show those dialogs.
* The dialogs live in the platform cache (`steam/cached/Receipt_*.res`), not in
  the emulator's files. A client whose cache lacks them will fall back.
* `get_card_type()` only knows Visa and MasterCard.
