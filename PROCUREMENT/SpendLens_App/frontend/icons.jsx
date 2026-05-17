// SpendLens — icons (lucide-inspired, stroke-based)

const I = (paths, opts = {}) => function Icon({ size = 18, color = "currentColor", style }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color}
      strokeWidth={opts.sw || 1.7} strokeLinecap="round" strokeLinejoin="round" style={style}>
      {paths}
    </svg>
  );
};

const Icons = {
  Logo:       I(<><path d="M12 3 3 8v8l9 5 9-5V8l-9-5Z"/><path d="m3 8 9 5 9-5"/><path d="M12 13v8"/></>),
  Dashboard:  I(<><rect x="3" y="3"  width="8" height="9" rx="1.5"/><rect x="13" y="3" width="8" height="5" rx="1.5"/><rect x="13" y="10" width="8" height="11" rx="1.5"/><rect x="3" y="14" width="8" height="7" rx="1.5"/></>),
  DeepDive:   I(<><circle cx="11" cy="11" r="7"/><path d="m20 20-4.3-4.3"/><path d="M11 8v6M8 11h6"/></>),
  Compliance: I(<><path d="M9 12.5 11 14.5 15.5 10"/><path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3Z"/></>),
  Icarus:     I(<><path d="M12 2 4 7v6c0 4 3 7 8 9 5-2 8-5 8-9V7l-8-5Z"/><circle cx="12" cy="11" r="2.2"/><path d="M12 4v3M12 15v4M5.5 8.5l2 1M16.5 8.5l-2 1"/></>),
  Strategy:   I(<><path d="M3 21V8"/><path d="M9 21V13"/><path d="M15 21V10"/><path d="M21 21V4"/><path d="M3 21h18"/></>),
  Supplier:   I(<><path d="M12 3 3 7v4c0 1 .5 2 1.5 2.5l7 3.5 7-3.5c1-.5 1.5-1.5 1.5-2.5V7l-9-4Z"/><path d="M3 12v5l9 4 9-4v-5"/></>),
  CLM:        I(<><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/></>),
  Search:     I(<><circle cx="11" cy="11" r="7"/><path d="m20 20-4.3-4.3"/></>),
  Bell:       I(<><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21a2 2 0 0 0 4 0"/></>),
  Menu:       I(<><path d="M4 7h16M4 12h16M4 17h16"/></>),
  ChevR:      I(<><path d="m9 6 6 6-6 6"/></>),
  ChevD:      I(<><path d="m6 9 6 6 6-6"/></>),
  ChevU:      I(<><path d="m6 15 6-6 6 6"/></>),
  Plus:       I(<><path d="M12 5v14M5 12h14"/></>),
  X:          I(<><path d="M6 6l12 12M18 6 6 18"/></>),
  Filter:     I(<><path d="M3 5h18l-7 9v5l-4 2v-7L3 5Z"/></>),
  Download:   I(<><path d="M12 4v12"/><path d="m7 11 5 5 5-5"/><path d="M5 20h14"/></>),
  Upload:     I(<><path d="M12 20V8"/><path d="m7 13 5-5 5 5"/><path d="M5 4h14"/></>),
  Bolt:       I(<><path d="M13 2 4 14h7l-2 8 9-12h-7l2-8Z"/></>),
  Spark:      I(<><path d="M5 3v4M3 5h4M19 17v4M17 19h4M13 4 11 9 6 11l5 2 2 5 2-5 5-2-5-2-2-5Z"/></>),
  Alert:      I(<><path d="M12 3 2 21h20L12 3Z"/><path d="M12 10v5"/><circle cx="12" cy="18" r=".5"/></>),
  Calendar:   I(<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v4M16 3v4"/></>),
  Eye:        I(<><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>),
  Mic:        I(<><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></>),
  Send:       I(<><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7Z"/></>),
  Sparkles:   I(<><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.5 5.5l2 2M16.5 16.5l2 2M5.5 18.5l2-2M16.5 7.5l2-2"/></>),
  Cog:        I(<><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4.9a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.5a7 7 0 0 0-2 1.2L5 5.8 3 9.2l2 1.6a7 7 0 0 0 0 2.4l-2 1.6 2 3.4 2.4-.9a7 7 0 0 0 2 1.2L10 21h4l.5-2.5a7 7 0 0 0 2-1.2l2.5.9 2-3.4-2-1.6c.1-.4.1-.8.1-1.2Z"/></>),
  ArrowUp:    I(<><path d="M12 19V5M5 12l7-7 7 7"/></>),
  ArrowDn:    I(<><path d="M12 5v14M5 12l7 7 7-7"/></>),
  Doc:        I(<><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5"/></>),
  Refresh:    I(<><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/></>),
  Star:       I(<><path d="m12 3 2.6 6.3 6.4.5-5 4 1.6 6.2L12 17l-5.6 3 1.6-6.2-5-4 6.4-.5L12 3Z"/></>),
  Trash:      I(<><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M6 6l1 14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-14"/></>),
  Globe:      I(<><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a13 13 0 0 1 0 18M12 3a13 13 0 0 0 0 18"/></>),
  Tag:        I(<><path d="M20 11.5V4h-7.5L3 13.5 10.5 21 20 11.5Z"/><circle cx="8" cy="8" r="1.5"/></>),
  Check:      I(<><path d="M20 6 9 17l-5-5"/></>),
  Info:       I(<><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M12 12v4"/></>),
};

Object.assign(window, { Icons });
