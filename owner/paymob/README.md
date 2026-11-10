# Mizan's card payment page (Paymob iframe)

A branded card form that Paymob hosts on its own domain (an Accept "iframe"): the owner
pays for a subscription here, and card details go straight to Paymob, never to Mizan.

| File | What it is |
|---|---|
| `card.html` | The form. Paymob's script submits `#paymob_checkout` and reads the `[paymob_field]` inputs: `card_number` (digits), `card_holdername`, `card_expiry_mm`, `card_expiry_yy` (2 digits), `card_cvn`, `subtype=CARD`. |
| `card.css` | Mizan's palette and type; RTL page, LTR card and numbers. |
| `card.js` | Formatting, Luhn/expiry/CVV checks with Arabic messages, the live card preview (Visa, Mastercard, Meeza, Amex; flips for the CVV), and the order summary read from the payment key in the URL (amount, billing name, expiry countdown, `extra.description`). It never sends card data itself. |
| `upload.py` | Creates the iframe through Paymob's API, or updates it with `PAYMOB_IFRAME_ID`. |

```bash
PAYMOB_API_KEY=… python owner/paymob/upload.py                    # create → prints the id
PAYMOB_API_KEY=… PAYMOB_IFRAME_ID=<id> python owner/paymob/upload.py  # update after edits
```

Preview locally: join the three files into one page and open it with
`?payment_token=<a test payment key>`.

**Status (2026-11-10):** Paymob refuses to create iframes on merchant 1064562 ("Something
went wrong", from the API and the dashboard) until the account is fully activated; see #65.
