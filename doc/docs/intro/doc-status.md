---
sidebar_position: 2
title: Documentation Status
---

# Documentation Status

🚧 **The UDB documentation site is under active construction.** This page tracks the completion status of all planned documentation sections, so you can see at a glance what exists and what's coming.

## Status Legend

- ✅ **Complete** — Documentation is written, reviewed, and ready to use
- 🚧 **In Progress** — Partially complete; some sections may be missing or outdated
- 📋 **Planned** — Documentation is planned but not yet written

---

## Introduction

| Section | Status | Notes |
|---------|--------|-------|
| What is UDB? | ✅ Complete | Core overview complete |
| Current State | 📋 Planned | Maturity and use case coverage |

## Getting Started

| Section | Status | Notes |
|---------|--------|-------|
| For Users | 📋 Planned | CLI, Ruby gem, Python bindings |
| For Specification Writers | 📋 Planned | Adding extensions, instructions, CSRs |
| For Developers | 📋 Planned | Contributing code, writing generators |
| FAQ / How-Do-I | 📋 Planned | Common questions and solutions |

## Concepts

| Section | Status | Notes |
|---------|--------|-------|
| Configurations | 🚧 In Progress | Overview exists, details pending |
| Data Pipeline | 📋 Planned | Overlay merge, resolution, inheritance |
| Conditions System | 📋 Planned | How conditions work in the database |

## The Database (spec/)

| Section | Status | Notes |
|---------|--------|-------|
| Overview | 📋 Planned | Database structure and organization |
| Table Reference | 📋 Planned | Documentation for each table |
| Custom Overlays | 📋 Planned | How to customize the database |
| Schema Reference | 🚧 In Progress | Auto-generated from JSON Schema |

## IDL Language

| Section | Status | Notes |
|---------|--------|-------|
| Overview | ✅ Complete | Core concepts and use cases |
| Data Types | ✅ Complete | Bits, Boolean, structs, enums |
| Literals | ✅ Complete | Integer, array, string literals |
| Operators | ✅ Complete | Full precedence table |
| Variables & Constants | ✅ Complete | Declaration and usage |
| Type Conversions | ✅ Complete | Casting and implicit conversions |
| Builtins | ✅ Complete | Built-in functions reference |
| Control Flow | ✅ Complete | if/else, loops, switch |
| Functions | ✅ Complete | Declaration, calls, generated functions |
| Scope Rules | ✅ Complete | Variable and function scoping |
| In Instructions | ✅ Complete | How IDL appears in instruction definitions |
| In CSRs | ✅ Complete | CSR-specific IDL usage |
| For Spec Writers | ✅ Complete | Guide for writing IDL specs |
| For C Users | ✅ Complete | IDL from a C perspective |
| For Verilog Users | ✅ Complete | IDL from a hardware perspective |
| Common Misunderstandings | ✅ Complete | FAQ and gotchas |
| Quick Reference | ✅ Complete | Cheat sheet |
| Standard Library | ✅ Complete | Standard library functions |
| idlc Compiler | 🚧 In Progress | Compiler tool documentation |

## Tools

| Section | Status | Notes |
|---------|--------|-------|
| Overview | 📋 Planned | Tool ecosystem overview |
| udb gem | 📋 Planned | Main database interface |
| udb-gen gem | 📋 Planned | Artifact generation |
| idlc gem | 📋 Planned | IDL compiler |
| udb_helpers gem | 📋 Planned | Template helpers |
| idl_highlighter gem | 📋 Planned | Syntax highlighting |
| bin/generate | 📋 Planned | Generator wrapper script |
| bin/regress | 📋 Planned | Regression test runner |
| bin/chore | 📋 Planned | Repository maintenance |

## Generators

| Section | Status | Notes |
|---------|--------|-------|
| Overview | 📋 Planned | What generators produce |
| C++ ISS | 📋 Planned | Instruction Set Simulator |
| C Header | 📋 Planned | Encoding headers |
| Go | 📋 Planned | Go definitions |
| SystemVerilog | 📋 Planned | Decode packages |

## Contributing

| Section | Status | Notes |
|---------|--------|-------|
| Code Contributions | 📋 Planned | How to contribute code |
| Data Contributions | 📋 Planned | Adding spec data |
| Commit Conventions | 📋 Planned | Commit message format |
| Code Review | 📋 Planned | Review process |
| Docs Site Architecture | 📋 Planned | How this site is built |

---

## Timeline

This documentation is being written incrementally as the site is built. The IDL language documentation is mostly complete (converted from existing AsciiDoc sources), while other sections are being written from scratch.

**Priority order:**
1. Introduction and Getting Started (enabling new users)
2. Concepts (understanding the architecture)
3. Tools and Generators (practical usage)
4. Database reference (for advanced users)
5. Contributing guides (for contributors)

Check back regularly for updates, or [watch the repository](https://github.com/riscv/riscv-unified-db) to be notified of new documentation.
