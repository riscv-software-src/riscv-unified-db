// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: BSD-3-Clause-Clear

import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';
import styles from './index.module.css';

// Import UDB logo as React component for CSS variable support
import UdbLogo from '@site/static/img/udb-navbar.svg';

function HeroSection(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={styles.hero}>
      <div className="container">
        <div className={styles.heroContent}>
          <UdbLogo className={styles.heroLogo} />
          <Heading as="h1" className={styles.heroTitle}>
            RISC-V Unified Database
          </Heading>
          <p className={styles.heroTagline}>{siteConfig.tagline}</p>
          <div className={styles.heroButtons}>
            <Link
              className="button button--primary button--lg"
              href="https://riscv.github.io/riscv-unified-db/"
              target="_blank"
              rel="noopener noreferrer">
              Browse the Spec
            </Link>
            <Link
              className="button button--secondary button--lg"
              to="/docs/getting-started/users">
              Get Started
            </Link>
            <Link
              className="button button--secondary button--lg"
              href="https://github.com/riscv/riscv-unified-db"
              target="_blank"
              rel="noopener noreferrer">
              GitHub
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
}

function WhatIsUDB(): ReactNode {
  return (
    <section className={styles.section}>
      <div className="container">
        <p className={styles.summary}>
          The RISC-V Unified Database (UDB) is a comprehensive, machine-readable repository
          of the RISC-V ISA specification. It serves as the single source of truth for
          instruction encodings, CSR definitions, and architectural state, enabling automated
          generation of documentation, simulators, compilers, and verification tools.
        </p>
        <Link to="/docs/intro/what-is-udb" className={styles.learnMore}>
          Learn more →
        </Link>
      </div>
    </section>
  );
}

interface FeatureCard {
  icon: string;
  title: string;
  description: string;
  link: string;
  isExternal?: boolean;
}

const features: FeatureCard[] = [
  {
    icon: '🔍',
    title: 'Browse the RISC-V spec',
    description: 'Explore the complete ISA specification with interactive tables, instruction details, and CSR definitions.',
    link: 'https://riscv.github.io/riscv-unified-db/',
    isExternal: true,
  },
  {
    icon: '⚙️',
    title: 'Generate artifacts for your design',
    description: 'Use UDB tools to generate C headers, SystemVerilog, documentation, and more for your custom RISC-V implementation.',
    link: '/docs/getting-started/users',
  },
  {
    icon: '📝',
    title: 'Contribute data',
    description: 'Add new extensions, instructions, or CSRs to the database using our structured IDL format.',
    link: '/docs/getting-started/spec-writers',
  },
  {
    icon: '🛠️',
    title: 'Build tools / contribute code',
    description: 'Create new generators, integrate UDB into your toolchain, or contribute to the project.',
    link: '/docs/getting-started/developers',
  },
];

function FeatureCards(): ReactNode {
  return (
    <section className={styles.section}>
      <div className="container">
        <Heading as="h2" className={styles.sectionTitle}>
          I want to...
        </Heading>
        <div className={styles.featureGrid}>
          {features.map((feature, idx) => (
            <Link
              key={idx}
              to={feature.link}
              className={styles.featureCard}
              {...(feature.isExternal && {
                target: '_blank',
                rel: 'noopener noreferrer',
              })}>
              <div className={styles.featureIcon}>{feature.icon}</div>
              <Heading as="h3" className={styles.featureTitle}>
                {feature.title}
              </Heading>
              <p className={styles.featureDescription}>{feature.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

interface Generator {
  name: string;
  description: string;
  link: string;
}

const generators: Generator[] = [
  {
    name: 'C Headers',
    description: 'Instruction encoding and CSR definitions',
    link: '/docs/generators/c-header',
  },
  {
    name: 'SystemVerilog',
    description: 'Decode packages for RTL design',
    link: '/docs/generators/sverilog',
  },
  {
    name: 'Documentation',
    description: 'Extension documentation and PDF generation',
    link: '/docs/generators/overview',
  },
];

function GeneratorShowcase(): ReactNode {
  return (
    <section className={`${styles.section} ${styles.showcaseSection}`}>
      <div className="container">
        <Heading as="h2" className={styles.sectionTitle}>
          What can UDB generate?
        </Heading>
        <div className={styles.generatorGrid}>
          {generators.map((gen, idx) => (
            <Link key={idx} to={gen.link} className={styles.generatorCard}>
              <Heading as="h4" className={styles.generatorName}>
                {gen.name}
              </Heading>
              <p className={styles.generatorDescription}>{gen.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

const quickLinks = [
  {label: 'IDL Language Reference', to: '/docs/idl/overview'},
  {label: 'Schema Reference', to: '/docs/schemas/overview'},
  {label: 'Configuration Format', to: '/docs/configuration/overview'},
  {label: 'FAQ / How-Do-I', to: '/docs/getting-started/developers/faq'},
  {label: 'GitHub Issues', href: 'https://github.com/riscv/riscv-unified-db/issues'},
];

function QuickLinks(): ReactNode {
  return (
    <section className={styles.quickLinksSection}>
      <div className="container">
        <div className={styles.quickLinks}>
          {quickLinks.map((link, idx) => (
            <Link
              key={idx}
              {...(link.to ? {to: link.to} : {href: link.href})}
              className={styles.quickLink}
              {...(link.href && {
                target: '_blank',
                rel: 'noopener noreferrer',
              })}>
              {link.label}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title={siteConfig.title}
      description={siteConfig.tagline}>
      <HeroSection />
      <main>
        <WhatIsUDB />
        <FeatureCards />
        <GeneratorShowcase />
        <QuickLinks />
      </main>
    </Layout>
  );
}
