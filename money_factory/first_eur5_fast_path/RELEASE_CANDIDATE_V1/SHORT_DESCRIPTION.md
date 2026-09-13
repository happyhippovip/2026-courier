# Agent Context Trimmer

**Audit and optimize repeated system prompt tokens across your AI coding agent sessions.**

When you work with AI coding agents in Cursor, Windsurf, Cline, or Gemini, your editor re-transmits active workspace rule files on conversational turns. When projects accumulate duplicate directives, embedded multi-line data structures, or obsolete boilerplate across `.cursorrules` and `.gemini/rules/`, this repeated context silently consumes prompt window capacity.

**Agent Context Trimmer** is a zero-dependency, local command-line tool that audits your workspace rules. It analyzes your files in under 50ms on tested benchmark fixtures, highlights duplicate instructions across markdown sections, flags embedded code blocks exceeding 25 lines, and lets you model estimated repeated token overhead against published model pricing (Claude 3.5 Sonnet, GPT-4o, and Gemini 1.5 Pro).

Available as an offline, standalone tool for an initial test price of **€5**.
