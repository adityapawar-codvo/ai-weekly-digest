#!/bin/bash
# This script helps verify that GitHub Secrets are correctly set up.
# Run this after setting secrets in GitHub Settings -> Secrets and variables -> Actions

echo "GitHub Secrets Verification"
echo "==========================="
echo ""
echo "To set up secrets in your GitHub repository:"
echo "1. Go to: https://github.com/YOUR-USERNAME/mailing_agent/settings/secrets/actions"
echo "2. Click 'New repository secret'"
echo "3. For each variable below, add it with the EXACT name (case-sensitive):"
echo ""
echo "Required secrets:"
echo "  ✓ OPENROUTER_API_KEY       (from https://openrouter.ai/keys)"
echo "  ✓ OPENROUTER_MODEL         (e.g., 'openrouter/auto' or 'google/gemini-2.5-flash')"
echo "  ✓ BREVO_API_KEY            (from https://app.brevo.com/settings/keys/api)"
echo "  ✓ SENDER_EMAIL             (must be verified in Brevo)"
echo "  ✓ SENDER_NAME              (e.g., 'AI Weekly Digest')"
echo "  ✓ MAINTAINER_EMAIL         (your email)"
echo "  ✓ DRY_RUN                  (true/false)"
echo ""
echo "After adding secrets, wait a few seconds then run the workflow:"
echo "  Go to: Actions -> AI Weekly Digest -> Run workflow -> Select mode 'build'"
