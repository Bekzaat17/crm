"use client";
import { useState } from "react";
import { useWidth } from "@/lib/use-width";
import { bucketLabel, number } from "./format";
import { SERIES, type Bucket, type SeriesPoint } from "./types";

const HEIGHT = 240;
const PAD = { top: 12, right: 12, bottom: 28, left: 36 };

/** Целые «круглые» деления оси: шаг 1, 2 или 5 × 10ⁿ. */
function ticks(max: number, count = 4) {
  if (max <= 0) return [0, 1];
  const raw = max / count;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = Math.max(
    1,
    [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw)!,
  );
  const result = [];
  for (let value = 0; value <= max + step - 1e-9; value += step)
    result.push(Math.round(value));
  return result;
}

export function TrendChart({
  points,
  bucket,
}: {
  points: SeriesPoint[];
  bucket: Bucket;
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const max = Math.max(
    0,
    ...points.flatMap((p) => SERIES.map((s) => p[s.key])),
  );
  const yTicks = ticks(max);
  const top = yTicks[yTicks.length - 1];
  const plotW = width - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const step = points.length > 1 ? plotW / (points.length - 1) : 0;
  const x = (i: number) =>
    PAD.left + (points.length > 1 ? i * step : plotW / 2);
  const y = (v: number) => PAD.top + plotH - (v / top) * plotH;
  const labelEvery = Math.max(1, Math.ceil(points.length / (plotW / 72)));
  const showMarkers = points.length <= 16;
  const current = active === null ? null : points[active];

  const pick = (clientX: number, box: DOMRect) => {
    const offset = clientX - box.left - PAD.left;
    const index = step ? Math.round(offset / step) : 0;
    setActive(Math.min(points.length - 1, Math.max(0, index)));
  };

  return (
    <div className="chart-frame" ref={ref}>
      <svg
        width={width}
        height={HEIGHT}
        role="img"
        aria-label="Динамика: новые обращения, поступления и отказы"
        tabIndex={0}
        onMouseMove={(e) =>
          pick(e.clientX, e.currentTarget.getBoundingClientRect())
        }
        onMouseLeave={() => setActive(null)}
        onBlur={() => setActive(null)}
        onKeyDown={(e) => {
          if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
          e.preventDefault();
          const delta = e.key === "ArrowLeft" ? -1 : 1;
          setActive((value) =>
            Math.min(
              points.length - 1,
              Math.max(0, (value ?? (delta > 0 ? -1 : points.length)) + delta),
            ),
          );
        }}
      >
        {yTicks.map((value) => (
          <g key={value}>
            <line
              className="chart-grid"
              x1={PAD.left}
              x2={width - PAD.right}
              y1={y(value)}
              y2={y(value)}
            />
            <text
              className="chart-axis"
              x={PAD.left - 8}
              y={y(value) + 4}
              textAnchor="end"
            >
              {number(value)}
            </text>
          </g>
        ))}
        {points.map((point, i) =>
          i % labelEvery === 0 ? (
            <text
              key={point.start}
              className="chart-axis"
              x={x(i)}
              y={HEIGHT - 8}
              textAnchor={
                points.length > 1 && i === 0
                  ? "start"
                  : i === points.length - 1 && points.length > 1
                    ? "end"
                    : "middle"
              }
            >
              {bucketLabel(point.start, bucket)}
            </text>
          ) : null,
        )}
        {current && (
          <line
            className="chart-crosshair"
            x1={x(active!)}
            x2={x(active!)}
            y1={PAD.top}
            y2={PAD.top + plotH}
          />
        )}
        {SERIES.map((series) => (
          <g key={series.key} style={{ color: series.color }}>
            <polyline
              className="chart-line"
              points={points
                .map((p, i) => `${x(i)},${y(p[series.key])}`)
                .join(" ")}
            />
            {points.map((p, i) =>
              showMarkers || i === active ? (
                <circle
                  key={p.start}
                  className="chart-marker"
                  cx={x(i)}
                  cy={y(p[series.key])}
                  r={4}
                />
              ) : null,
            )}
          </g>
        ))}
      </svg>
      {current && (
        <div
          className="chart-tooltip"
          role="status"
          style={{
            left: Math.min(Math.max(x(active!), 90), width - 90),
          }}
        >
          <span className="chart-tooltip-title">
            {bucketLabel(current.start, bucket, true)}
          </span>
          {SERIES.map((series) => (
            <span key={series.key} className="chart-tooltip-row">
              <i style={{ background: series.color }} aria-hidden />
              {series.label}
              <strong>{number(current[series.key])}</strong>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function TrendTable({
  points,
  bucket,
}: {
  points: SeriesPoint[];
  bucket: Bucket;
}) {
  return (
    <div className="table-scroll">
      <table className="analytics-table">
        <thead>
          <tr>
            <th>Период</th>
            {SERIES.map((s) => (
              <th key={s.key} className="numeric">
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {points.map((p) => (
            <tr key={p.start}>
              <td>{bucketLabel(p.start, bucket, true)}</td>
              {SERIES.map((s) => (
                <td key={s.key} className="numeric">
                  {number(p[s.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
