export function label(name: string, count: number): string {
  const noun = count === 1 ? "item" : "items";
  return `${name}: ${count} ${noun}`;
}

export function pages(total: number, size: number): number {
  if (size <= 0) {
    throw new Error("size must be positive");
  }
  return Math.ceil(total / size);
}

// The banner is plain text. Callers escape it before display.
export function banner(title: string): string {
  const line = "=".repeat(title.length + 4);
  return `${line}\n= ${title} =\n${line}`;
}
