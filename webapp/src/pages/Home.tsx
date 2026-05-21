import { type MouseEvent, type ReactNode, useRef } from 'react'
import {
  motion,
  useMotionTemplate,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from 'framer-motion'
import { Link } from 'react-router-dom'
import { VIOCI_LOGO_SRC } from '../brand'
import { useAuthStore } from '../state/auth'

const capabilities = [
  {
    label: 'AI Blueprint Transcription',
    code: 'CV-01',
    copy: 'Convert diagrams, payload sheets, and PDFs into structured mission data.',
  },
  {
    label: 'Payload Validation',
    code: 'PL-14',
    copy: 'Check mass, geometry, interfaces, and vehicle envelopes before review gates.',
  },
  {
    label: 'Simulation Infrastructure',
    code: 'SIM-09',
    copy: 'Run mission-aware analysis from a connected component graph.',
  },
  {
    label: 'Launch Readiness Analysis',
    code: 'LR-22',
    copy: 'Track constraints, risks, and subsystem readiness in one operating picture.',
  },
]

const headlineWords = ['Launch', 'Intelligence', 'Infrastructure']

const telemetry = [
  'ingest blueprint stack',
  'normalize component registry',
  'validate payload envelope',
  'simulate mission readiness',
]

const stats = [
  ['184', 'schema nodes tracked'],
  ['37', 'mission checks automated'],
  ['12ms', 'telemetry graph sync'],
]

function MagneticLink({
  to,
  className,
  children,
}: {
  to: string
  className?: string
  children: ReactNode
}) {
  const reduceMotion = useReducedMotion()
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const springX = useSpring(x, { stiffness: 320, damping: 22, mass: 0.5 })
  const springY = useSpring(y, { stiffness: 320, damping: 22, mass: 0.5 })

  const onMouseMove = (event: MouseEvent<HTMLAnchorElement>) => {
    if (reduceMotion) return
    const bounds = event.currentTarget.getBoundingClientRect()
    x.set((event.clientX - bounds.left - bounds.width / 2) * 0.16)
    y.set((event.clientY - bounds.top - bounds.height / 2) * 0.22)
  }

  return (
    <Link
      to={to}
      className={className}
      onMouseMove={onMouseMove}
      onMouseLeave={() => {
        x.set(0)
        y.set(0)
      }}
    >
      <motion.span className="home-magnetic-content" style={{ x: springX, y: springY }}>
        {children}
      </motion.span>
    </Link>
  )
}

function BriefingSection({
  className = '',
  children,
  ariaLabel,
}: {
  className?: string
  children: ReactNode
  ariaLabel?: string
}) {
  const reduceMotion = useReducedMotion()
  return (
    <motion.section
      aria-label={ariaLabel}
      className={`home-briefing-section ${className}`}
      initial={reduceMotion ? false : { opacity: 0, y: 72, filter: 'blur(18px)' }}
      whileInView={reduceMotion ? undefined : { opacity: 1, y: 0, filter: 'blur(0px)' }}
      viewport={{ once: true, margin: '-16% 0px' }}
      transition={{ type: 'spring', stiffness: 95, damping: 24, mass: 0.9 }}
    >
      {children}
    </motion.section>
  )
}

export function Home() {
  const pageRef = useRef<HTMLElement>(null)
  const token = useAuthStore((s) => s.token)
  const primaryHref = token ? '/workspace' : '/signup'
  const primaryLabel = token ? 'Open mission OS' : 'Request mission access'
  const reduceMotion = useReducedMotion()
  const pointerX = useMotionValue(0)
  const pointerY = useMotionValue(0)
  const springX = useSpring(pointerX, { stiffness: 38, damping: 24, mass: 1.2 })
  const springY = useSpring(pointerY, { stiffness: 38, damping: 24, mass: 1.2 })
  const parallaxX = useTransform(springX, [-0.5, 0.5], [-26, 26])
  const parallaxY = useTransform(springY, [-0.5, 0.5], [-18, 18])
  const lightX = useTransform(springX, [-0.5, 0.5], ['38%', '62%'])
  const lightY = useTransform(springY, [-0.5, 0.5], ['28%', '68%'])
  const cursorLight = useMotionTemplate`radial-gradient(circle at ${lightX} ${lightY}, rgba(126, 160, 151, 0.18), rgba(75, 117, 108, 0.08) 24%, transparent 58%), radial-gradient(circle at 50% 20%, rgba(238, 243, 241, 0.06), transparent 30%)`
  const { scrollYProgress } = useScroll({ target: pageRef, offset: ['start start', 'end end'] })
  const scanY = useTransform(scrollYProgress, [0, 1], ['0%', '26%'])
  const depthY = useTransform(scrollYProgress, [0, 1], [0, -160])

  const onMouseMove = (event: MouseEvent<HTMLElement>) => {
    if (reduceMotion) return
    const bounds = event.currentTarget.getBoundingClientRect()
    pointerX.set((event.clientX - bounds.left) / bounds.width - 0.5)
    pointerY.set((event.clientY - bounds.top) / bounds.height - 0.5)
  }

  return (
    <motion.main ref={pageRef} className="home-page" onMouseMove={onMouseMove}>
      <motion.div
        className="home-cursor-light"
        aria-hidden
        style={{ x: parallaxX, y: parallaxY, background: cursorLight }}
      />
      <motion.div className="home-depth-field" aria-hidden style={{ y: depthY }}>
        <span className="home-glow home-glow-a" />
        <span className="home-glow home-glow-b" />
        <span className="home-glow home-glow-c" />
        <span className="home-orbital-grid" />
        <span className="home-particle-field" />
      </motion.div>
      <motion.div className="home-scanlines" aria-hidden style={{ y: scanY }} />
      <div className="home-noise" aria-hidden />

      <nav className="home-nav" aria-label="VIOCI home navigation">
        <Link to="/" className="home-brand" aria-label="VIOCI home">
          <img src={VIOCI_LOGO_SRC} alt="VIOCI" className="home-brand-logo vioci-logo" />
        </Link>
        <div className="home-nav-actions">
          <MagneticLink to="/login" className="home-nav-link">
            Log in
          </MagneticLink>
          <MagneticLink to={primaryHref} className="home-nav-link home-nav-link-primary">
            {primaryLabel}
          </MagneticLink>
        </div>
      </nav>

      <section className="home-hero">
        <motion.div
          className="home-status"
          initial={reduceMotion ? false : { opacity: 0, y: -18 }}
          animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 120, damping: 18 }}
        >
          <span className="home-status-dot" />
          LIVE MISSION INFRASTRUCTURE
        </motion.div>

        <motion.h1
          className="home-headline"
          initial="hidden"
          animate="show"
          variants={{
            hidden: {},
            show: { transition: { staggerChildren: 0.11, delayChildren: 0.15 } },
          }}
        >
          {headlineWords.map((word) => (
            <motion.span
              key={word}
              variants={{
                hidden: { opacity: 0, y: 64, filter: 'blur(18px)' },
                show: {
                  opacity: 1,
                  y: 0,
                  filter: 'blur(0px)',
                  transition: { type: 'spring', stiffness: 110, damping: 20, mass: 0.9 },
                },
              }}
            >
              {word}
            </motion.span>
          ))}
        </motion.h1>

        <motion.p
          className="home-subhead"
          initial={reduceMotion ? false : { opacity: 0, y: 30, filter: 'blur(10px)' }}
          animate={reduceMotion ? undefined : { opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ type: 'spring', stiffness: 90, damping: 22, delay: 0.55 }}
        >
          Vioci turns spacecraft schematics, launch constraints, and subsystem evidence into a
          living operating layer for mission teams.
        </motion.p>

        <motion.div
          className="home-hero-actions"
          initial={reduceMotion ? false : { opacity: 0, y: 24 }}
          animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 110, damping: 22, delay: 0.72 }}
        >
          <MagneticLink to={primaryHref} className="home-cta home-cta-primary">
            {primaryLabel}
          </MagneticLink>
          <MagneticLink to="/login" className="home-cta home-cta-secondary">
            Enter platform
          </MagneticLink>
        </motion.div>

        <motion.div
          className="home-orbit-visual"
          aria-label="Animated mission telemetry visualization"
          style={{ x: parallaxX, y: parallaxY }}
          initial={reduceMotion ? false : { opacity: 0, scale: 0.92, filter: 'blur(18px)' }}
          animate={reduceMotion ? undefined : { opacity: 1, scale: 1, filter: 'blur(0px)' }}
          transition={{ type: 'spring', stiffness: 60, damping: 18, delay: 0.85 }}
        >
          <div className="home-orbit-core">
            <span>VIOCI</span>
          </div>
          <motion.svg
            viewBox="0 0 720 360"
            className="home-orbit-svg"
            aria-hidden
            animate={reduceMotion ? undefined : { rotate: 360 }}
            transition={{ duration: 90, repeat: Infinity, ease: 'linear' }}
          >
            <ellipse cx="360" cy="180" rx="280" ry="94" />
            <ellipse cx="360" cy="180" rx="210" ry="72" />
            <ellipse cx="360" cy="180" rx="135" ry="45" />
            <motion.path
              d="M96 210 C210 68 462 56 623 154"
              pathLength={1}
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 2.8, ease: 'easeInOut', delay: 1 }}
            />
          </motion.svg>
          <span className="home-orbit-node home-orbit-node-a" />
          <span className="home-orbit-node home-orbit-node-b" />
          <span className="home-orbit-node home-orbit-node-c" />
          <div className="home-telemetry-strip">
            {telemetry.map((line, index) => (
              <motion.span
                key={line}
                initial={reduceMotion ? false : { opacity: 0, y: 12 }}
                animate={reduceMotion ? undefined : { opacity: [0.42, 1, 0.42], y: 0 }}
                transition={{
                  duration: 3.8,
                  repeat: Infinity,
                  delay: index * 0.55,
                  ease: 'easeInOut',
                }}
              >
                {line}
              </motion.span>
            ))}
          </div>
        </motion.div>
      </section>

      <BriefingSection className="home-problem">
        <p>
          Launch operations still run on <span>fragmented spreadsheets</span>, <span>PDFs</span>,
          and <span>disconnected tooling</span>.
        </p>
      </BriefingSection>

      <BriefingSection className="home-capabilities" ariaLabel="Platform capabilities">
        <p className="home-kicker">Platform capabilities</p>
        <div className="home-capability-field">
          <span className="home-connector-line home-connector-line-a" />
          <span className="home-connector-line home-connector-line-b" />
          {capabilities.map((item, index) => (
            <motion.article
              className="home-capability-card"
              key={item.label}
              whileHover={reduceMotion ? undefined : { y: -10, scale: 1.015 }}
              transition={{ type: 'spring', stiffness: 220, damping: 22 }}
              style={{ translateY: reduceMotion ? 0 : index % 2 ? 14 : -8 }}
            >
              <span className="home-capability-code">{item.code}</span>
              <h2>{item.label}</h2>
              <p>{item.copy}</p>
            </motion.article>
          ))}
        </div>
      </BriefingSection>

      <BriefingSection className="home-system-section">
        <p className="home-kicker">Live launch pipeline</p>
        <div className="home-system-visual" aria-label="Simulated launch pipeline visualization">
          <svg viewBox="0 0 960 420" aria-hidden>
            <defs>
              <linearGradient id="home-flow-gradient" x1="0" x2="1" y1="0" y2="0">
                <stop offset="0%" stopColor="rgba(75,117,108,0)" />
                <stop offset="45%" stopColor="rgba(126,160,151,0.9)" />
                <stop offset="100%" stopColor="rgba(75,117,108,0)" />
              </linearGradient>
            </defs>
            <path className="home-system-grid-path" d="M70 288 C240 104 376 120 520 220 S735 350 890 118" />
            <motion.path
              className="home-system-flow"
              d="M70 288 C240 104 376 120 520 220 S735 350 890 118"
              strokeDasharray="120 620"
              animate={reduceMotion ? undefined : { strokeDashoffset: [620, 0] }}
              transition={{ duration: 7.5, repeat: Infinity, ease: 'linear' }}
            />
            {[96, 258, 438, 610, 790].map((cx, index) => (
              <motion.circle
                key={cx}
                cx={cx}
                cy={[270, 154, 184, 284, 190][index]}
                r={index === 2 ? 9 : 6}
                animate={reduceMotion ? undefined : { r: [6, 10, 6], opacity: [0.45, 1, 0.45] }}
                transition={{ duration: 2.6, repeat: Infinity, delay: index * 0.28 }}
              />
            ))}
          </svg>
          <div className="home-system-readout">
            <span>SCHEMATIC INGEST</span>
            <span>REGISTRY NORMALIZATION</span>
            <span>PAYLOAD CHECKS</span>
            <span>MISSION READINESS</span>
          </div>
        </div>
      </BriefingSection>

      <BriefingSection className="home-trust">
        <p>Testing with active launch integration workflows.</p>
        <div className="home-stats">
          {stats.map(([value, label]) => (
            <motion.div
              className="home-stat"
              key={label}
              whileInView={reduceMotion ? undefined : { opacity: [0.35, 1], y: [18, 0] }}
              viewport={{ once: true }}
              transition={{ type: 'spring', stiffness: 100, damping: 20 }}
            >
              <strong>{value}</strong>
              <span>{label}</span>
            </motion.div>
          ))}
        </div>
      </BriefingSection>

      <BriefingSection className="home-final-cta">
        <h2>Build the infrastructure behind modern space missions.</h2>
        <MagneticLink to={primaryHref} className="home-cta home-cta-primary">
          {primaryLabel}
        </MagneticLink>
      </BriefingSection>
    </motion.main>
  )
}
