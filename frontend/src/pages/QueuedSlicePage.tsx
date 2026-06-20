interface QueuedSlicePageProps {
  title: string;
  description: string;
}

export function QueuedSlicePage({ title, description }: QueuedSlicePageProps) {
  return (
    <section className="rounded-md border border-line bg-panel p-6 shadow-panel">
      <p className="text-sm font-medium text-accent">Migration slice queued</p>
      <h1 className="mt-2 text-2xl font-semibold text-ink">{title}</h1>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{description}</p>
    </section>
  );
}
