# Brand asset optimization

Original mark and original TTF files are unchanged. Derivatives use the original pixels, with Lanczos downsampling and lossless WebP encoding. No logo redraw or recoloring.

| Asset | Bytes | Purpose |
| --- | ---: | --- |
| `assets/darkhorse-mark-96.webp` | 5,190 | 96 × 96 logo |
| `assets/darkhorse-mark-192.webp` | 14,534 | 192 × 192 logo |
| `assets/darkhorse-mark-384.webp` | 61,308 | 384 × 384 logo |
| `assets/darkhorse-social-1200x630.png` | 110,252 | Open Graph / Twitter large-image preview |

## Font budget

Nine WOFF2 faces total **136,804 bytes** (133.6 KiB). The full set is below the 150 KB budget. Browser downloads only used faces.

Inter 400/500/600/700/800, Barlow Condensed 600/700/800, and Anton 400 retain their original family identities and shapes. Subsets cover basic Latin, Latin-1, general punctuation, euro/trademark, and common UI arrows and mathematical signs. Barlow hinting is removed; Inter and Anton hinting is retained. Emoji and characters outside the subset use system fallback.

`fonts.css` now owns all nine face declarations. Remove the older Anton TTF declaration in `darkhorse-brand.css` to avoid superseding the optimized face.

The social preview uses exact brand colors, the existing horse mark, actual Anton/Inter fonts, /// marks, and the locked tagline. No predicted scores, statistics, or promotional performance claims.
