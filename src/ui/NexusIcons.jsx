import React from 'react';

// Familiar banking symbols on a shared 32px grid with rounded strokes.
// These are decorative; the surrounding control supplies its accessible label.
function Glyph({ size = 24, strokeWidth = 1.7, className = '', children, ...props }) {
  return <svg width={size} height={size} viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" className={`nexus-glyph ${className}`} {...props}>{children}</svg>;
}

export function TransferIcon(props) {
  return <Glyph {...props}><path d="M5 9h22m-6-6 6 6-6 6M27 23H5m6-6-6 6 6 6"/></Glyph>;
}
export function BillIcon(props) {
  return <Glyph {...props}><path d="M7 3h13l5 5v21l-4-3-5 3-5-3-4 3Z"/><path d="M20 3v6h5M11 13h10M11 18h10M11 23h5"/></Glyph>;
}
export function SavingsIcon(props) {
  return <Glyph {...props}><circle cx="15" cy="5" r="3.2"/><path d="M8 13c3-3 11-3 15 0l3-2v6l3 2v5h-4l-2 5h-4v-4h-7v4H8l-2-7c-4-1-4-7 0-8M5 16c-4 0-4-5-1-5M12 14h6"/><circle cx="23" cy="18" r="1" fill="currentColor" stroke="none"/></Glyph>;
}
export function WithdrawIcon(props) {
  return <Glyph {...props}><rect x="5" y="3" width="22" height="12" rx="2"/><circle cx="16" cy="9" r="3"/><path d="M16 18v8m-5-5 5 5 5-5M4 24v5h24v-5"/></Glyph>;
}
export function AccountIcon(props) {
  return <Glyph {...props}><rect x="4" y="9" width="24" height="19" rx="3"/><path d="M5 10V6a2 2 0 0 1 2-2h17v5"/><rect x="20" y="16" width="9" height="7" rx="1.5"/><circle cx="24" cy="19.5" r="1" fill="currentColor" stroke="none"/></Glyph>;
}
export function PlanIcon(props) {
  return <Glyph {...props}><rect x="4" y="6" width="24" height="23" rx="3"/><path d="M10 3v6M22 3v6M4 12h24m-14 8 4 4 8-8"/></Glyph>;
}
export function ForecastIcon(props) {
  return <Glyph {...props}><path d="M4 4v24h24M9 21v-7m7 7V8m7 13V4"/></Glyph>;
}
export function ProtectionIcon(props) {
  return <Glyph {...props}><path d="m16 3 11 4v9c0 6-5 10-11 13C10 26 5 22 5 16V7Z"/><path d="m11 16 4 4 7-8"/></Glyph>;
}
export function ReserveIcon(props) {
  return <Glyph {...props}><ellipse cx="16" cy="7" rx="11" ry="4"/><path d="M5 7v7c0 5 22 5 22 0V7M5 14v7c0 5 22 5 22 0v-7M5 21v4c0 5 22 5 22 0v-4"/></Glyph>;
}
export function TransferSettingsIcon(props) {
  return <Glyph {...props}><path d="M4 8h6m6 0h12M4 24h13m6 0h5"/><circle cx="13" cy="8" r="3"/><circle cx="20" cy="24" r="3"/></Glyph>;
}
export function HomeIcon(props) {
  return <Glyph {...props}><path d="m3 15 13-11 13 11M6 13v15h20V13M13 28V18h6v10"/></Glyph>;
}
export function ProfileIcon(props) {
  return <Glyph {...props}><circle cx="16" cy="9" r="6"/><path d="M5 29v-3c0-10 22-10 22 0v3"/></Glyph>;
}
