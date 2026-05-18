# Panama Postal Codes

Optional Panama postal-code support for partner addresses.

The module decodes full Panama postal codes such as `ACC99-PJ42W` from
`res.partner.zip` and stores:

- whether the code is valid under the official geospatial code format
- decoded latitude and longitude
- decoded precision level
- estafeta prefix, when present in the code

Existing legacy short ZIP values are left alone and are not rejected.

The port also includes local GeoJSON point-in-polygon helpers for
estafeta and political-division enrichment. The module does not perform
automatic network lookups.

## Provenance

The codec is ported from `kass507/panama-postal`, copyright (c) 2026
kass507, originally MIT licensed. The MIT license permits sublicensing;
this Odoo module is distributed under LGPL-3 like the rest of the Panama
localization repository. The original copyright notice is preserved in
`NOTICE`.
