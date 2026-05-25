import clsx from "clsx";

export function cn(...values: Array<string | false | null | undefined>): string {
  return clsx(values);
}

export function formatLabel(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
