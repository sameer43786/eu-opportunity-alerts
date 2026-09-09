# Global Opportunity Alerts

An automated GitHub Actions monitor for European short-term training, youth, education, research, cybersecurity, IT, artificial-intelligence and workflow-automation opportunities.

**By Sameer Ali**  
Contact: [sameer43786@gmail.com](mailto:sameer43786@gmail.com)

## What it does

Every day, the workflow:

1. searches Europe-focused official opportunity sources through public search RSS results;
2. retrieves each result page;
3. scores transparent eligibility, audience, topic and activity terms from `config.yaml`;
4. rejects explicit age-restricted calls by default;
5. labels age eligibility as `explicitly no limit`, `not stated`, or `explicit limit detected`;
6. removes already-seen links;
7. creates a GitHub Issue for new matches;
8. optionally sends the same alert by email.

Initial sources cover the SALTO European Training Calendar, EURAXESS, the European Youth Portal, and the European Commission Funding & Tenders pages. All source domains and queries are editable.

> This tool finds candidates; it cannot guarantee eligibility. Always verify the official call, deadline, residence rules, funding and applicant category before applying.

## Repository contents

```text
.
├── .github/workflows/opportunity-monitor.yml
├── data/seen.json
├── docs/PDF_INSIGHTS.md
├── tests/test_monitor.py
├── .gitignore
├── config.yaml
├── LICENSE
├── opportunity_monitor.py
├── README.md
└── requirements.txt
```

## Fastest GitHub setup

1. Create a new **public or private** GitHub repository without initializing it with a README.
2. Upload all extracted project files, including the `.github` directory.
3. Open the repository's **Actions** tab.
4. If prompted, click **I understand my workflows, go ahead and enable them**.
5. Select **Monitor European opportunities**.
6. Click **Run workflow**, keep `main`, and click the green **Run workflow** button.
7. After the run completes, open the **Issues** tab. A successful run with new matches creates an issue labelled `opportunity-alert`.

The scheduled workflow runs daily at 07:17 UTC. GitHub may delay scheduled jobs during busy periods. In public repositories, GitHub can disable scheduled workflows after long periods without repository activity; running it manually or committing a change reactivates it.

## Required GitHub permissions

The workflow includes:

```yaml
permissions:
  contents: write
  issues: write
```

These permissions allow it to create alerts and commit only `data/seen.json` for deduplication. If organisation policy restricts workflow tokens, open:

`Settings → Actions → General → Workflow permissions`

Select **Read and write permissions**, then save.

## Optional email alerts

GitHub Issue alerts work without adding secrets. For email too, open:

`Settings → Secrets and variables → Actions → New repository secret`

Add:

| Secret | Example for Gmail |
| --- | --- |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `465` |
| `SMTP_USERNAME` | your sender email |
| `SMTP_PASSWORD` | a Gmail app password, not your normal password |
| `ALERT_EMAIL_TO` | `sameer43786@gmail.com` |

Use a dedicated sender account and app password. Never place passwords in `config.yaml`, the workflow file, or source code.

## Customize eligibility and topics

Edit `config.yaml`. Important controls include:

- `minimum_score`: raise it for fewer, stronger matches; lower it for broader discovery;
- `require_any_groups`: at least one of these audience/activity groups must match;
- `require_topic_groups`: at least one selected topic group must match;
- `age.reject_explicit_limits`: excludes detected age caps when `true`;
- `groups`: terms and weights for researchers, youth organisations, short training, cybersecurity, AI, automation and related interests;
- `sources`: official domains and search queries.

Changes take effect on the next manual or scheduled run.

## Run locally

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python opportunity_monitor.py --dry-run
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python opportunity_monitor.py --dry-run
```

`--dry-run` prints results without creating issues, sending email or changing deduplication state.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Responsible operation and limitations

- Searches depend on public indexing and source-page availability, so no monitor can guarantee complete coverage.
- Sites may change markup, block automated retrieval, publish incomplete snippets or state eligibility only in attachments.
- Search-source errors are isolated so one failing source does not stop the others.
- The script uses a descriptive user agent, conservative delays and bounded result counts.
- Confirm every application on the official page. Do not rely solely on inferred age, deadline, funding, residence or professional eligibility.

## License

MIT License. See [LICENSE](LICENSE).
