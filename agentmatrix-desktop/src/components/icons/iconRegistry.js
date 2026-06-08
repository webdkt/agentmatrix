/**
 * ZEN v2 Icon Registry — Alias Map
 *
 * Only non-standard aliases that can't be auto-resolved from Lucide names.
 * Standard Lucide icons (e.g. "cloud", "file-search", "wallet") are auto-resolved
 * in MIcon.vue via kebab-case → PascalCase lookup.
 */

import {
  ArrowLeft, RefreshCw, CircleCheck,
  Maximize2, Minimize2, ShieldOff, Plug, AtSign,
  Sparkles, Radio, Bot, Atom, Braces,
  Play, Pause,
  MonitorPlay, Brain,
  Send, X,
} from 'lucide-vue-next'

export const iconMap = {
  // ─── Short aliases ───
  x: X,
  close: X,
  play: Play,
  pause: Pause,

  // ─── Tabler fallback names ───
  'arrow-back-up': ArrowLeft,
  at: AtSign,
  'circle-check': CircleCheck,
  'arrows-maximize': Maximize2,
  'arrows-minimize': Minimize2,
  'refresh-cw': RefreshCw,
  'shield-off': ShieldOff,
  'plug-connected': Plug,
  'monitor-play': MonitorPlay,

  // ─── Brand / custom aliases ───
  logo: Sparkles,
  dispatch: Radio,
  'brain-off': Brain,
  agent: Bot,
  'agent-dispatch': Send,
  robot: Bot,
  'atom-2': Atom,
  api: Braces,
}
