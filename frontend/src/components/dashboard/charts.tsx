"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const TOOLTIP_STYLE = {
  background: "#111827",
  border: "1px solid #263042",
  borderRadius: "12px",
  fontSize: "12px",
  color: "#e5e7eb",
};

/** Horizontal bar chart fed by live data (e.g. volume by channel/status). */
export function UsageBars({ data }: { data: { name: string; value: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#263042" horizontal={false} />
        <XAxis type="number" stroke="#64748b" fontSize={11} tickLine={false} axisLine={false} />
        <YAxis type="category" dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} width={90} />
        <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "rgba(6,182,212,0.08)" }} />
        <Bar dataKey="value" fill="#06b6d4" radius={[0, 8, 8, 0]} name="Requests" />
      </BarChart>
    </ResponsiveContainer>
  );
}
