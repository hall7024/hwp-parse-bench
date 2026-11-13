#!/usr/bin/env node
// kordoc 어댑터. 사용법: node adapters/kordoc/run.mjs [--table-format=gfm] <입력 파일> <출력 파일>
// - 외부 통신을 막고(KORDOC_OFFLINE=1) OCR을 끈다. 원본 파일의 글만 읽는다.
// - 기본은 kordoc 기본 출력(병합 칸이 있는 표는 HTML), --table-format=gfm 이면 모든 표를 GFM 파이프 표로 낸다.
// - 실패하면 stderr에 한 줄을 쓰고 1로 끝낸다.
import { writeFile } from "node:fs/promises"

process.env.KORDOC_OFFLINE = "1"

function fail(message) {
  process.stderr.write(`${String(message).split("\n")[0].slice(0, 300)}\n`)
  process.exit(1)
}

const args = process.argv.slice(2)
const flags = args.filter((a) => a.startsWith("--"))
const [src, dst] = args.filter((a) => !a.startsWith("--"))
if (!src || !dst) fail("사용법: node adapters/kordoc/run.mjs [--table-format=gfm] <입력> <출력>")
const unknown = flags.filter((f) => f !== "--table-format=gfm")
if (unknown.length) fail(`알 수 없는 옵션: ${unknown.join(" ")}`)

const options = { ocr: false, images: false }
if (flags.includes("--table-format=gfm")) options.tableFormat = "gfm"

try {
  const { parse } = await import("kordoc")
  const result = await parse(src, options)
  if (!result.success) fail(`${result.code ?? "PARSE_FAILED"}: ${result.error ?? "변환 실패"}`)
  await writeFile(dst, result.markdown ?? "", "utf8")
} catch (error) {
  fail(`${error?.name ?? "Error"}: ${error?.message ?? error}`)
}
