import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// Import order is load-bearing. All four stylesheets are here, in the order
// they must load, rather than scattered across the components that use them.
//
// `tokens.css` first: it defines the custom properties every other stylesheet
// and every component references. Putting it first is also what makes "no raw
// hex outside this file" a rule with a single, obvious place to check.
//
// `fonts.css` next — the @font-face declarations, pointing at files in
// public/fonts/. There is no <link> to Google Fonts anywhere in this project:
// the dashboard has to render correctly with no network.
//
// `leaflet.css` before index.css, and this is the whole reason the map's
// stylesheet is imported here rather than inside MapPanel. index.css re-skins
// Leaflet's controls in tokens, and those rules TIE with Leaflet's own on
// specificity — a tie is broken by source order, so whichever loads last wins.
// Imported from the component it loaded last, and the zoom buttons and the
// scale bar stayed white on a near-black dashboard.
//
// `index.css` last: it imports Tailwind and publishes the tokens as utilities
// via `@theme inline`, so it has to come after the tokens it is naming — and
// it carries the Leaflet overrides, which have to come after Leaflet.
import './tokens.css'
import './fonts.css'
import 'leaflet/dist/leaflet.css'
import './index.css'

import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
