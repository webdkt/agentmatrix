/**
 * MERIDIAN Icon Registry
 *
 * Custom SVG icons: thin 1.5px strokes, square caps, no fill.
 * Copperplate engraving aesthetic.
 *
 * Icons not in this registry fall back to Tabler Icons.
 */

export const iconRegistry = {
  // ─── Logo ───
  logo: `<rect x="4" y="4" width="16" height="16" rx="1"/>
         <line x1="4" y1="12" x2="20" y2="12"/>
         <line x1="12" y1="4" x2="12" y2="20"/>`,

  // ─── Dispatch (App Icon) ───
  // Matrix node with dispatch lines - represents distributed cognition
  'dispatch': `<circle cx="12" cy="12" r="3"/>
               <line x1="12" y1="2" x2="12" y2="6"/>
               <line x1="12" y1="18" x2="12" y2="22"/>
               <line x1="2" y1="12" x2="6" y2="12"/>
               <line x1="18" y1="12" x2="22" y2="12"/>
               <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/>
               <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/>
               <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/>
               <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/>`,

  // ─── Actions ───
  send: `<path d="M22 2L11 13"/>
         <path d="M22 2L15 22L11 13L2 9L22 2Z"/>`,

  plus: `<line x1="12" y1="5" x2="12" y2="19"/>
         <line x1="5" y1="12" x2="19" y2="12"/>`,

  close: `<line x1="6" y1="6" x2="18" y2="18"/>
          <line x1="18" y1="6" x2="6" y2="18"/>`,

  check: `<polyline points="5 12 10 17 19 8"/>`,

  refresh: `<path d="M1 4V10H7"/>
            <path d="M23 20V14H17"/>
            <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10"/>
            <path d="M3.51 15A9 9 0 0 0 18.36 18.36L23 14"/>`,

  // ─── Navigation ───
  'arrow-left': `<line x1="19" y1="12" x2="5" y2="12"/>
                 <polyline points="12 19 5 12 12 5"/>`,

  'arrow-right': `<line x1="5" y1="12" x2="19" y2="12"/>
                  <polyline points="12 5 19 12 12 19"/>`,

  search: `<circle cx="11" cy="11" r="7"/>
           <line x1="21" y1="21" x2="16.65" y2="16.65"/>`,

  'chevron-right': `<polyline points="9 6 15 12 9 18"/>`,

  'chevron-down': `<polyline points="6 9 12 15 18 9"/>`,

  // ─── Communication ───
  mail: `<rect x="2" y="5" width="20" height="14" rx="1"/>
         <polyline points="2 5 12 13 22 5"/>`,

  'mail-off': `<path d="M22 5L12 13L9 10"/>
               <rect x="2" y="5" width="20" height="14" rx="1"/>
               <line x1="2" y1="5" x2="22" y2="19"/>`,

  'message-circle': `<path d="M21 11.5A8.38 8.38 0 0 1 12.5 21 8.38 8.38 0 0 1 4 12.5 8.38 8.38 0 0 1 12.5 4"/>
                     <path d="M21 11.5L21 3L16 7"/>`,

  messages: `<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>`,

  // ─── Agent ───
  brain: `<path d="M12 2C9 2 7 4 7 6.5C5.5 6.5 4 8 4 10C4 12 5.5 13.5 7.5 13.5C7.5 15.5 9 17 11 17H13C15 17 16.5 15.5 16.5 13.5C18.5 13.5 20 12 20 10C20 8 18.5 6.5 17 6.5C17 4 15 2 12 2Z"/>
         <line x1="12" y1="6" x2="12" y2="14"/>`,

  'brain-off': `<path d="M12 2C9 2 7 4 7 6.5C5.5 6.5 4 8 4 10C4 12 5.5 13.5 7.5 13.5"/>
                <path d="M16.5 13.5C18.5 13.5 20 12 20 10C20 8 18.5 6.5 17 6.5C17 4 15 2 12 2"/>
                <line x1="2" y1="2" x2="22" y2="22"/>`,

  // Agent Node - a hexagonal vessel (like a vessel icon), abstract autonomous entity
  'agent': `<polygon points="12,3 21,8 21,16 12,21 5,16 5,8"/>
            <line x1="12" y1="3" x2="12" y2="21"/>
            <line x1="5" y1="8" x2="18" y2="8"/>`,

  // Agent variant - dispatch node (concentric circles with crosshair)
  'agent-dispatch': `<circle cx="12" cy="12" r="8"/>
                     <circle cx="12" cy="12" r="3"/>
                     <line x1="12" y1="2" x2="12" y2="6"/>
                     <line x1="12" y1="18" x2="12" y2="22"/>
                     <line x1="2" y1="12" x2="6" y2="12"/>
                     <line x1="18" y1="12" x2="22" y2="12"/>`,

  // Legacy robot (keep for compatibility)
  robot: `<rect x="5" y="8" width="14" height="12" rx="1"/>
          <circle cx="9" cy="13" r="1.5"/>
          <circle cx="15" cy="13" r="1.5"/>
          <line x1="9" y1="18" x2="15" y2="18"/>
          <line x1="12" y1="4" x2="12" y2="8"/>
          <circle cx="12" cy="3" r="1"/>`,

  // ─── Settings ───
  settings: `<line x1="4" y1="6" x2="20" y2="6"/>
             <line x1="4" y1="12" x2="20" y2="12"/>
             <line x1="4" y1="18" x2="20" y2="18"/>
             <circle cx="8" cy="6" r="2"/>
             <circle cx="16" cy="12" r="2"/>
             <circle cx="10" cy="18" r="2"/>`,

  sliders: `<line x1="4" y1="6" x2="20" y2="6"/>
            <line x1="4" y1="12" x2="20" y2="12"/>
            <line x1="4" y1="18" x2="20" y2="18"/>
            <circle cx="8" cy="6" r="2"/>
            <circle cx="16" cy="12" r="2"/>
            <circle cx="10" cy="18" r="2"/>`,

  // ─── Content ───
  user: `<circle cx="12" cy="7" r="4"/>
         <path d="M4 21V18C4 16 6 14 8 14H16C18 14 20 16 20 18V21"/>`,

  folder: `<path d="M22 19V8C22 7 21 6 20 6H11L9 4H4C3 4 2 5 2 6V19C2 20 3 21 4 21H20C21 21 22 20 22 19Z"/>`,

  'folder-open': `<path d="M22 19V8C22 7 21 6 20 6H11L9 4H4C3 4 2 5 2 6V19C2 20 3 21 4 21H20C21 21 22 20 22 19Z"/>
                  <path d="M2 10H22"/>`,

  paperclip: `<path d="M21.44 11.05L12.25 20.24C10.13 22.36 6.69 22.36 4.57 20.24C2.45 18.12 2.45 14.68 4.57 12.56L13.76 3.37C15.13 2 17.34 2 18.71 3.37C20.08 4.75 20.08 6.96 18.71 8.33L9.51 17.53C8.83 18.21 7.72 18.21 7.04 17.53C6.36 16.85 6.36 15.74 7.04 15.06L15.53 6.57"/>`,

  trash: `<polyline points="3 6 5 6 21 6"/>
          <path d="M19 6V20C19 21 18 22 17 22H7C6 22 5 21 5 20V6"/>
          <path d="M8 6V4C8 3 9 2 10 2H14C15 2 16 3 16 4V6"/>`,

  copy: `<rect x="8" y="8" width="12" height="12" rx="1"/>
         <path d="M16 8V4C16 3 15 2 14 2H4C3 2 2 3 2 4V14C2 15 3 16 4 16H8"/>`,

  pencil: `<path d="M17 3C17.5 2.5 18.5 2.5 19 3L21 5C21.5 5.5 21.5 6.5 21 7L7 21L3 22L4 18L17 3Z"/>`,

  // ─── Status ───
  'alert-circle': `<circle cx="12" cy="12" r="9"/>
                   <line x1="12" y1="8" x2="12" y2="12"/>
                   <circle cx="12" cy="16" r="0.5" fill="currentColor"/>`,

  'alert-triangle': `<path d="M10.29 3.86L1.82 18C1.64 18.32 1.54 18.69 1.54 19.07C1.54 20.13 2.41 21 3.47 21H20.53C21.59 21 22.46 20.13 22.46 19.07C22.46 18.69 22.36 18.32 22.18 18L13.71 3.86C13.35 3.24 12.69 2.87 12 2.87C11.31 2.87 10.65 3.24 10.29 3.86Z"/>
                     <line x1="12" y1="9" x2="12" y2="13"/>
                     <circle cx="12" cy="17" r="0.5" fill="currentColor"/>`,

  'x-circle': `<circle cx="12" cy="12" r="9"/>
               <line x1="9" y1="9" x2="15" y2="15"/>
               <line x1="15" y1="9" x2="9" y2="15"/>`,

  'check-circle': `<circle cx="12" cy="12" r="9"/>
                   <polyline points="9 12 11 14 15 10"/>`,

  'info-circle': `<circle cx="12" cy="12" r="9"/>
                  <line x1="12" y1="11" x2="12" y2="17"/>
                  <circle cx="12" cy="8" r="0.5" fill="currentColor"/>`,

  'shield-check': `<path d="M12 22S20 18 20 12V5L12 2L4 5V12C4 18 12 22 12 22Z"/>
                   <polyline points="9 12 11 14 15 10"/>`,

  shield: `<path d="M12 22S20 18 20 12V5L12 2L4 5V12C4 18 12 22 12 22Z"/>`,

  // ─── Views ───
  'layout-dashboard': `<rect x="3" y="3" width="7" height="7" rx="1"/>
                       <rect x="14" y="3" width="7" height="4" rx="1"/>
                       <rect x="3" y="14" width="7" height="7" rx="1"/>
                       <rect x="14" y="11" width="7" height="10" rx="1"/>`,

  grid: `<rect x="3" y="3" width="7" height="7" rx="1"/>
         <rect x="14" y="3" width="7" height="7" rx="1"/>
         <rect x="3" y="14" width="7" height="7" rx="1"/>
         <rect x="14" y="14" width="7" height="7" rx="1"/>`,

  // ─── Misc ───
  wand: `<path d="M15 4V2"/>
         <path d="M15 10V8"/>
         <path d="M11.5 6.5L10 5"/>
         <path d="M18.5 6.5L20 5"/>
         <path d="M11.5 11.5L10 13"/>
         <path d="M18.5 11.5L20 13"/>
         <path d="M15 16V14"/>
         <path d="M5 21L16 10"/>`,

  'eye-off': `<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20C7 20 2.73 16.39 1 12A18.45 18.45 0 0 1 5.06 5.06"/>
              <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4C17 4 21.27 7.61 23 12A18.5 18.5 0 0 1 19.73 14.73"/>
              <line x1="1" y1="1" x2="23" y2="23"/>`,

  eye: `<path d="M1 12S5 4 12 4S23 12 23 12S19 20 12 20S1 12 1 12Z"/>
        <circle cx="12" cy="12" r="3"/>`,

  'player-pause': `<rect x="6" y="4" width="4" height="16" rx="1"/>
                   <rect x="14" y="4" width="4" height="16" rx="1"/>`,

  'player-play': `<polygon points="5 3 19 12 5 21 5 3"/>`,

  bolt: `<path d="M13 2L3 14H12L11 22L21 10H12L13 2Z"/>`,

  rocket: `<path d="M4.5 16.5C3 18 3 21 3 21S6 21 7.5 19.5C8.1 18.9 8.1 18 7.7 17.3"/>
           <path d="M12 12L6 18"/>
           <path d="M12 12C12 12 14 4 21 2C21 9 13 11 13 11"/>
           <circle cx="18" cy="7" r="1"/>`,

  // at: removed (temporarily unused)

  inbox: `<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/>
          <path d="M5.45 5.11L2 12V20C2 21 3 22 4 22H20C21 22 22 21 22 20V12L18.55 5.11C18.38 4.77 18.04 4.56 17.67 4.5H6.33C5.96 4.56 5.62 4.77 5.45 5.11Z"/>`,

  upload: `<path d="M21 15V19C21 20 20 21 19 21H5C4 21 3 20 3 19V15"/>
           <polyline points="17 8 12 3 7 8"/>
           <line x1="12" y1="3" x2="12" y2="15"/>`,

  database: `<ellipse cx="12" cy="5" rx="9" ry="3"/>
             <path d="M21 5V11C21 13 17 16 12 16S3 13 3 11V5"/>
             <path d="M21 11V17C21 19 17 22 12 22S3 19 3 17V11"/>`,

  cpu: `<rect x="4" y="4" width="16" height="16" rx="1"/>
        <rect x="9" y="9" width="6" height="6"/>
        <line x1="9" y1="1" x2="9" y2="4"/>
        <line x1="15" y1="1" x2="15" y2="4"/>
        <line x1="9" y1="20" x2="9" y2="23"/>
        <line x1="15" y1="20" x2="15" y2="23"/>
        <line x1="1" y1="9" x2="4" y2="9"/>
        <line x1="1" y1="15" x2="4" y2="15"/>
        <line x1="20" y1="9" x2="23" y2="9"/>
        <line x1="20" y1="15" x2="23" y2="15"/>`,

  link: `<path d="M10 13C10.4 13.8 11 14.4 11.7 14.8"/>
         <path d="M14 11C13.6 10.2 13 9.6 12.3 9.2"/>
         <path d="M18 7A5 5 0 0 0 8.5 10.5L10 12"/>
         <path d="M6 17A5 5 0 0 0 15.5 13.5L14 12"/>`,

  'dots-vertical': `<circle cx="12" cy="5" r="1"/>
                    <circle cx="12" cy="12" r="1"/>
                    <circle cx="12" cy="19" r="1"/>`,

  'atom-2': `<circle cx="12" cy="12" r="1"/>
             <path d="M12 2C12 2 20 8 20 12C20 16 12 22 12 22C12 22 4 16 4 12C4 8 12 2 12 2Z"/>
             <path d="M2.5 8C6 10 6 14 2.5 16"/>
             <path d="M21.5 8C18 10 18 14 21.5 16"/>`,

  api: `<path d="M4 17L10 11L4 5"/>
        <line x1="12" y1="19" x2="20" y2="19"/>`,

  flask: `<path d="M9 3H15"/>
          <path d="M10 3V7L4 18C3 20 5 22 7 22H17C19 22 21 20 20 18L14 7V3"/>`,

  help: `<circle cx="12" cy="12" r="9"/>
         <path d="M9 9C9 7.5 10 6.5 12 6.5C14 6.5 15 7.5 15 9C15 11 12 11 12 14"/>
         <circle cx="12" cy="17" r="0.5" fill="currentColor"/>`,

  'help-circle': `<circle cx="12" cy="12" r="9"/>
                  <path d="M9 9C9 7.5 10 6.5 12 6.5C14 6.5 15 7.5 15 9C15 11 12 11 12 14"/>
                  <circle cx="12" cy="17" r="0.5" fill="currentColor"/>`,

  file: `<path d="M14 2H6C5 2 4 3 4 4V20C4 21 5 22 6 22H18C19 22 20 21 20 20V8L14 2Z"/>
         <polyline points="14 2 14 8 20 8"/>`,

  // ─── Loading ───
  loader: `<line x1="12" y1="2" x2="12" y2="6"/>
           <line x1="12" y1="18" x2="12" y2="22"/>
           <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/>
           <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/>
           <line x1="2" y1="12" x2="6" y2="12"/>
           <line x1="18" y1="12" x2="22" y2="12"/>
           <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/>
           <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/>`,
}
