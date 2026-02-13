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
- URLs are validated using the `isSafeUrl()` function (both in JavaScript and Python) to ensure they start with `http://` or `https://`
- This prevents `javascript:` pseudo-protocol XSS attacks
- Invalid URLs are not rendered as links

#### Content Security Policy
- A comprehensive Content Security Policy (CSP) is implemented via meta tag
- **Scripts**: Restricted to self and trusted CDN (unpkg.com for Leaflet) - **no inline scripts allowed**
- **Styles**: Allows inline styles and trusted sources (Google Fonts, unpkg.com)
- **Images**: HTTPS sources only
- **Fonts**: Self and Google Fonts only
- Helps mitigate XSS and data injection attacks

#### External Scripts
- All application JavaScript is in external files (`barnehage_app.js`, `barnehage_data.js`)
- No inline event handlers or inline scripts
- CSP enforces this separation for maximum security

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

1. **No inline scripts** - All JavaScript code is in external files, enforced by CSP
2. **No inline event handlers** - All event binding is done via JavaScript
3. **rel="noopener"** - All external links include `rel="noopener"` to prevent window.opener exploitation
4. **HTTPS-only external resources** - All external resources are loaded over HTTPS
5. **Input validation** - Numeric inputs are validated and bounded
6. **URL protocol validation** - All URLs are validated before use in links
7. **Error handling** - Errors are caught and don't expose sensitive information

## Reporting Security Issues

If you discover a security vulnerability in this project, please report it by:
1. Opening an issue on GitHub (for non-critical issues)
2. Contacting the repository owner directly for critical security issues

Please do not publicly disclose security vulnerabilities until they have been addressed.
