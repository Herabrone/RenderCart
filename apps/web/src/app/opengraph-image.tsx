import { ImageResponse } from "next/og";
export const alt = "RenderCart — Less busywork. More done.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export default function Image() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: 70,
        background: "#f8f7f3",
        color: "#252621",
        fontFamily: "sans-serif",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          fontSize: 30,
          fontWeight: 700,
        }}
      >
        <span
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 48,
            height: 48,
            background: "#b94324",
            borderRadius: 13,
            color: "white",
          }}
        >
          ↗
        </span>
        RenderCart
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          fontSize: 88,
          fontWeight: 700,
          letterSpacing: -5,
          lineHeight: 1.05,
        }}
      >
        <span>Less busywork.</span>
        <span style={{ color: "#b94324" }}>More done.</span>
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 21,
          color: "#66685e",
        }}
      >
        <span>Your everyday workbench.</span>
        <span>Files · Ideas · Everyday tasks</span>
      </div>
    </div>,
    size,
  );
}
