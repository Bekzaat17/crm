"use client";
import { useState } from "react";
import { useWidth } from "@/lib/use-width";
import { bucketLabel, number } from "./format";
import { SERIES, type Bucket, type SeriesPoint } from "./types";

const HEIGHT = 220;
const PAD = { top: 12, right: 4, bottom: 26, left: 30 };
const GAP = 2;

/** Целые «круглые» деления оси: шаг 1, 2 или 5 × 10ⁿ. */
function ticks(max: number) {
  const raw = Math.max(1, max) / 4;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = Math.max(
    1,
    [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw)!,
  );
  const result = [];
  for (let value = 0; value < Math.max(1, max) + step; value += step)
    result.push(value);
  return result;
}

/** Обращения и поступления по периодам: два столбца в группе. */
export function ColumnChart({
  points,
  bucket,
}: {
  points: SeriesPoint[];
  bucket: Bucket;
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const yTicks = ticks(
    Math.max(
      0,
      ...points.map((p) => p.created),
      ...points.map((p) => p.admitted),
    ),
  );
  const top = yTicks[yTicks.length - 1];
  const plotW = width - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const slot = plotW / Math.max(1, points.length);
  const bar = Math.min(24, Math.max(4, (slot * 0.7 - GAP) / 2));
  const y = (v: number) => PAD.top + plotH - (v / top) * plotH;
  const labelEvery = Math.max(1, Math.ceil(points.length / (plotW / 56)));
  const current = active === null ? null : points[active];

  return (
    <div className="chart-frame" ref={ref} onMouseLeave={() => setActive(null)}>
      <svg
        width={width}
        height={HEIGHT}
        role="img"
        aria-label="Обращения и поступления по периодам"
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
        {points.map((point, i) => {
          const center = PAD.left + slot * (i + 0.5);
          return (
            <g key={point.start}>
              {i === active && (
                <rect
                  className="chart-hover"
                  x={center - slot / 2}
                  y={PAD.top}
                  width={slot}
                  height={plotH}
                />
              )}
              {SERIES.map((series, s) => {
                const value = point[series.key];
                const h = Math.max(0, y(0) - y(value));
                const x = s === 0 ? center - GAP / 2 - bar : center + GAP / 2;
                const r = Math.min(4, h, bar / 2);
                // Скругление только у вершины столбца, основание прямое.
                return value ? (
                  <path
                    key={series.key}
                    fill={series.color}
                    d={`M${x},${y(0)}V${y(value) + r}q0,-${r} ${r},-${r}h${bar - 2 * r}q${r},0 ${r},${r}V${y(0)}Z`}
                  />
                ) : null;
              })}
              {i % labelEvery === 0 && (
                <text
                  className="chart-axis"
                  x={center}
                  y={HEIGHT - 6}
                  textAnchor="middle"
                >
                  {bucketLabel(point.start, bucket)}
                </text>
              )}
              <rect
                className="chart-hit"
                x={center - slot / 2}
                y={PAD.top}
                width={slot}
                height={plotH}
                tabIndex={0}
                aria-label={`${bucketLabel(point.start, bucket, true)}: обращения ${point.created}, поступили ${point.admitted}`}
                onMouseEnter={() => setActive(i)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
              />
            </g>
          );
        })}
      </svg>
      {current && (
        <div
          className="chart-tooltip"
          style={{
            left: Math.min(
              Math.max(PAD.left + slot * (active! + 0.5), 80),
              width - 80,
            ),
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
