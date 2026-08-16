# Authenticated n8n orchestration

Ledgerline's optional n8n workflow is a transport and routing layer. It does not parse documents, assign final statuses, or keep its own duplicate list. The API remains the system of record.

## Security boundary

The workflow calls `POST /api/v1/integrations/n8n/documents` over the Compose network at `http://api:8000`. The route accepts one `file` multipart field and requires `X-Ledgerline-Key`. Existing API routes are unchanged.

n8n binds to `127.0.0.1:5678`; keep it local or place it behind authenticated access control. Do not expose the integration endpoint or n8n form directly to the public internet. The exported workflow contains expressions for secrets, but no secret values or credential bindings.

## Configure and start

1. Copy `.env.example` to `.env` if needed.
2. Generate independent, high-entropy values for `N8N_API_KEY` and `N8N_ENCRYPTION_KEY`. Do not reuse a user password or commit either value.
3. Start the optional profile:

   ```powershell
   docker compose --profile n8n up --build --wait --wait-timeout 180
   ```

4. Open `http://127.0.0.1:5678`, complete n8n owner setup, and import `n8n/workflows/ledgerline-document-intake.json`.

The API fails closed with `503` if `N8N_API_KEY` is empty. Missing or incorrect request credentials return `401`.

## Bind external credentials

The exported workflow intentionally has no credential IDs. In n8n:

1. Create an **Header Auth** credential whose name is `X-Ledgerline-Key` and whose value exactly matches `N8N_API_KEY`. Bind it to all three Ledgerline HTTP Request nodes.
2. Bind a Gmail OAuth2 credential to both **Gmail Attachment Trigger** and **Download Gmail Attachments**. Use the minimum Gmail read scope supported by the nodes.
3. Bind an SMTP credential to **Email Operator**. Use a dedicated sender where possible.
4. Create the n8n variable `LEDGERLINE_OPERATOR_EMAIL` with the internal exception recipient.
5. Test each trigger manually with synthetic documents before activating the workflow.

Never export credential values, OAuth tokens, execution data, real documents, recipient addresses, webhook IDs, or instance metadata into Git.

## Workflow behavior

- The internal form accepts exactly one PDF, TXT, or JSON file.
- Gmail polling selects messages with supported attachments and creates one item per attachment.
- Each file is sent with the bound Header Auth credential; the key never appears in the workflow definition.
- `approved` and `duplicate` responses finish silently.
- `review` sends an operator email containing the Ledgerline record response.
- `4xx` responses go directly to terminal failure without retry.
- `5xx` responses wait 2 seconds, retry, wait 4 seconds if needed, and make one final attempt.

Review and failure emails can contain extracted document metadata. Set an appropriate retention policy in n8n and avoid including original document contents in notifications.

## Rotate the service key

1. Stop the optional n8n profile to prevent requests during rotation.
2. Replace `N8N_API_KEY` in `.env` with a newly generated value.
3. Update the n8n Header Auth credential to the same new value, then recreate the API container.
4. Submit a synthetic document and verify a `201` response in the n8n execution.
5. Remove the old key from any external secret store or deployment configuration.

## Stop and remove

```powershell
docker compose --profile n8n down
```

The `n8n_data` volume persists credentials and workflow state. Use `docker compose --profile n8n down --volumes` only when intentionally deleting local n8n and database state.
