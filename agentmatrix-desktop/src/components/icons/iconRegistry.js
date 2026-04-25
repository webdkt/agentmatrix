/**
 * ZEN v2 Icon Registry — Lucide Icons
 *
 * All icons unified through Lucide. No custom SVGs.
 * Stroke: 1.75px, round caps, round joins.
 */

import {
  // Core UI
  Send, Plus, X, Check, RefreshCw,
  ArrowLeft, ArrowRight,
  Search, ChevronRight, ChevronDown,
  Mail, MailX, MessageCircle, MessagesSquare,
  Brain,
  Settings, SlidersHorizontal,
  User, Folder, FolderOpen,
  Paperclip, Trash2, Copy, Pencil,
  CircleAlert, TriangleAlert, CircleX, CircleCheck, Info,
  ShieldCheck, Shield,
  LayoutDashboard, Grid3x3,
  Wand2, EyeOff, Eye,
  Pause, Play,
  Zap, Rocket, Inbox, Upload,
  Database, Cpu, Link,
  EllipsisVertical, FlaskConical, CircleHelp,
  File, FileText,
  Square, Terminal, MonitorPlay, Moon, Bed, Loader2,

  // Former Tabler fallbacks
  Maximize2, Minimize2, ShieldOff, Plug, AtSign,

  // Attachment file types
  Image, Sheet, FileCode2, FileArchive, FileVideo2, FileAudio2,

  // Brand icon replacements
  Sparkles, Radio, Bot, Atom, Braces,
} from 'lucide-vue-next'

export const iconMap = {
  // ─── Core UI ───
  send: Send,
  plus: Plus,
  close: X,
  x: X,
  check: Check,
  refresh: RefreshCw,
  'arrow-left': ArrowLeft,
  'arrow-right': ArrowRight,
  search: Search,
  'chevron-right': ChevronRight,
  'chevron-down': ChevronDown,
  mail: Mail,
  'mail-off': MailX,
  'message-circle': MessageCircle,
  messages: MessagesSquare,
  brain: Brain,
  settings: Settings,
  sliders: SlidersHorizontal,
  user: User,
  folder: Folder,
  'folder-open': FolderOpen,
  paperclip: Paperclip,
  trash: Trash2,
  copy: Copy,
  pencil: Pencil,
  'alert-circle': CircleAlert,
  'alert-triangle': TriangleAlert,
  'x-circle': CircleX,
  'check-circle': CircleCheck,
  'info-circle': Info,
  'shield-check': ShieldCheck,
  shield: Shield,
  'layout-dashboard': LayoutDashboard,
  grid: Grid3x3,
  wand: Wand2,
  'eye-off': EyeOff,
  eye: Eye,
  'player-pause': Pause,
  'player-play': Play,
  bolt: Zap,
  rocket: Rocket,
  inbox: Inbox,
  upload: Upload,
  database: Database,
  cpu: Cpu,
  link: Link,
  'dots-vertical': EllipsisVertical,
  flask: FlaskConical,
  help: CircleHelp,
  'help-circle': CircleHelp,
  file: File,
  'file-text': FileText,
  square: Square,
  terminal: Terminal,
  'monitor-play': MonitorPlay,
  moon: Moon,
  bed: Bed,
  loader: Loader2,

  // ─── Brand icons (formerly custom SVGs) ───
  logo: Sparkles,
  dispatch: Radio,
  'brain-off': Brain,
  agent: Bot,
  'agent-dispatch': Send,
  robot: Bot,
  'atom-2': Atom,
  api: Braces,

  // ─── Former Tabler fallback names ───
  'arrow-back-up': ArrowLeft,
  at: AtSign,
  'circle-check': CircleCheck,
  'arrows-maximize': Maximize2,
  'arrows-minimize': Minimize2,
  play: Play,
  pause: Pause,
  'refresh-cw': RefreshCw,
  'shield-off': ShieldOff,
  'plug-connected': Plug,

  // ─── Attachment file types ───
  'file-image': Image,
  'file-spreadsheet': Sheet,
  'file-code': FileCode2,
  'file-zip': FileArchive,
  'file-video': FileVideo2,
  'file-music': FileAudio2,
}
