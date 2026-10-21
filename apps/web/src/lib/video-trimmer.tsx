"use client";

import { useEffect, useState } from "react";

export function VideoTrimmer({
  file,
  onChange,
}: {
  file: File | undefined;
  onChange: (startSeconds: number, endSeconds: number, ready: boolean) => void;
}) {
  const [source, setSource] = useState("");
  const [duration, setDuration] = useState(0);
  const [startSeconds, setStartSeconds] = useState(0);
  const [endSeconds, setEndSeconds] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!file) {
      setSource("");
      setDuration(0);
      setStartSeconds(0);
      setEndSeconds(0);
      setError("");
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    setSource(objectUrl);
    setDuration(0);
    setStartSeconds(0);
    setEndSeconds(0);
    setError("");
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  useEffect(() => {
    onChange(startSeconds, endSeconds, duration > 0 && endSeconds > startSeconds);
  }, [duration, endSeconds, onChange, startSeconds]);

  function handleMetadata(event: React.SyntheticEvent<HTMLVideoElement>) {
    const seconds = event.currentTarget.duration;
    if (!Number.isFinite(seconds) || seconds <= 0 || seconds > 10_800) {
      setError("This video has an unsupported duration. Video must be between 0 and 3 hours.");
      setDuration(0);
      return;
    }
    setDuration(seconds);
    setStartSeconds(0);
    setEndSeconds(seconds);
    setError("");
  }

  const safeStartMax = Math.max(0, duration - 0.1);
  const safeEndMin = Math.min(duration, startSeconds + 0.1);
  return <section className="mt-5 rounded-xl border border-slate-200 p-4 dark:border-slate-700" aria-label="Trim video">
    <h2 className="font-semibold">Choose the clip to keep</h2>
    <p className="mt-1 text-sm text-slate-500">Preview your video, then set the start and end of the MP4 clip.</p>
    {!file && <p className="mt-4 text-sm text-slate-500">Choose a video file to preview it.</p>}
    {source && <video src={source} controls playsInline preload="metadata" onLoadedMetadata={handleMetadata} onError={() => setError("This browser could not preview the selected video format.")} className="mt-4 max-h-[28rem] w-full rounded-lg bg-black" />}
    {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
    {duration > 0 && <div className="mt-4 grid gap-4 sm:grid-cols-2">
      <label className="text-sm font-medium">Start: {startSeconds.toFixed(1)} sec
        <input type="range" min={0} max={safeStartMax} step={0.1} value={Math.min(startSeconds, safeStartMax)} onChange={(event) => {
          const value = Number(event.target.value);
          setStartSeconds(value);
          if (endSeconds <= value) setEndSeconds(Math.min(duration, value + 0.1));
        }} className="mt-2 block w-full accent-violet-600" />
      </label>
      <label className="text-sm font-medium">End: {endSeconds.toFixed(1)} sec
        <input type="range" min={safeEndMin} max={duration} step={0.1} value={Math.max(endSeconds, safeEndMin)} onChange={(event) => setEndSeconds(Number(event.target.value))} className="mt-2 block w-full accent-violet-600" />
      </label>
    </div>}
    {duration > 0 && <p className="mt-2 text-xs text-slate-500">Selected clip: {Math.max(0, endSeconds - startSeconds).toFixed(1)} sec of {duration.toFixed(1)} sec.</p>}
  </section>;
}
