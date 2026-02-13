# Security

## Security Improvements

This document outlines the security measures implemented in this project.

### Cross-Site Scripting (XSS) Protection

#### HTML Escaping
- All user-generated content is escaped before rendering in HTML using the `escapeHtml()` function
- Map popups properly escape all data fields (barnehage name, bydel, address)
- Result cards escape all displayed data
- Python script uses `html.escape()` when generating the static map HTML file

#### URL Validation
- URLs are validated using the `isSafeUrl()` function to ensure they start with `http://` or `https://`
- This prevents `javascript:` pseudo-protocol XSS attacks
- Invalid URLs are not rendered as links

#### Content Security Policy
- A comprehensive Content Security Policy (CSP) is implemented via meta tag
- Restricts script sources to self and trusted CDNs (unpkg.com for Leaflet)
- Restricts style sources to self and trusted sources (Google Fonts, unpkg.com)
- Allows images from HTTPS sources only
- Helps mitigate XSS and data injection attacks

### API Keys

The Algolia API keys used in `data/extract_barnehage_data.py` are:
- **Read-only** public API keys provided by Oslo Kommune
- Intended for client-side use in public applications
- Access only public kindergarten data from Oslo Kommune's open data API
- Rate-limited by Algolia's infrastructure
- Not considered sensitive credentials

If you believe these keys should be rotated or have concerns about their exposure, please contact Oslo Kommune directly.

### External Dependencies

All external JavaScript and CSS libraries are loaded with Subresource Integrity (SRI) hashes:
- Leaflet 1.9.4 (both JS and CSS)

This ensures that the files haven't been tampered with.

### Security Best Practices

1. **No inline event handlers** - All event binding is done via JavaScript
2. **rel="noopener"** - All external links include `rel="noopener"` to prevent window.opener exploitation
3. **HTTPS-only external resources** - All external resources are loaded over HTTPS
4. **Input validation** - Numeric inputs are validated and bounded
5. **Error handling** - Errors are caught and don't expose sensitive information

## Reporting Security Issues

If you discover a security vulnerability in this project, please report it by:
1. Opening an issue on GitHub (for non-critical issues)
2. Contacting the repository owner directly for critical security issues

Please do not publicly disclose security vulnerabilities until they have been addressed.
