import { describe, expect, it } from "vitest";
import { cleanPhone, formatPhone, isValidPhone, maskPhone } from "./phone";

describe("phone helpers", () => {
  it("keeps digits and drops country and trunk prefixes", () => {
    expect(cleanPhone("98765 43210")).toBe("9876543210");
    expect(cleanPhone("+91 98765-43210")).toBe("9876543210");
    expect(cleanPhone("919876543210")).toBe("9876543210");
    expect(cleanPhone("09876543210")).toBe("9876543210");
    expect(cleanPhone("98765432101234")).toBe("9876543210");
  });

  it("accepts only Indian mobile numbers", () => {
    expect(isValidPhone("9876543210")).toBe(true);
    expect(isValidPhone("5876543210")).toBe(false);
    expect(isValidPhone("987654321")).toBe(false);
  });

  it("formats while typing and masks for display", () => {
    expect(formatPhone("98765")).toBe("98765");
    expect(formatPhone("9876543210")).toBe("98765 43210");
    expect(maskPhone("9876543210")).toBe("+91 98••• ••210");
  });
});
