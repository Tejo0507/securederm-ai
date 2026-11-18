"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useConfirm } from "@/components/ConfirmProvider";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import Button from "@/components/ui/Button";
import Notice from "@/components/ui/Notice";
import EmptyState from "@/components/ui/EmptyState";
import { formatBytes } from "@/components/ui/FileDrop";
import { IconDatabase, IconTrash } from "@/components/ui/icons";

const PAGE = 20;

interface StoredImage {
  name: string;
  size_bytes: number;
  uploaded_at: string;
}

interface ImagePage {
  total: number;
  items: StoredImage[];
}

/** The stored name is a content hash plus an extension; the first eight characters tell images apart. */
export const shortName = (name: string) => {
  const dot = name.lastIndexOf(".");
  return dot > 8 ? `${name.slice(0, 8)}…${name.slice(dot)}` : name;
};

/**
 * The images on this node, newest first, each with a button that erases just
 * that one. Only name, size and time are listed: the server never serves
 * pixels back. `refreshKey` reloads the list (after an upload or an erase
 * elsewhere); `onChange` tells the parent when this list erased something.
 */
export default function StoredImages({ refreshKey, onChange }: { refreshKey: number; onChange: () => void }) {
  const confirm = useConfirm();
  const [items, setItems] = useState<StoredImage[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [error, setError] = useState("");
  // How many rows are showing, so a reload keeps "Show more" progress.
  const shown = useRef(PAGE);

  const reload = useCallback(async (signal?: AbortSignal) => {
    try {
      const limit = Math.min(100, Math.max(PAGE, shown.current));
      const page = await apiFetch<ImagePage>(`/api/datasets/images?limit=${limit}`, { signal });
      setItems(page.items);
      setTotal(page.total);
      shown.current = Math.max(PAGE, page.items.length);
      setError("");
    } catch (err: unknown) {
      if (signal?.aborted) return;
      setItems((current) => current ?? []);
      setError(err instanceof Error ? err.message : "Could not load your images.");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void reload(controller.signal);
    return () => controller.abort();
  }, [refreshKey, reload]);

  async function showMore() {
    if (!items) return;
    setLoadingMore(true);
    try {
      const page = await apiFetch<ImagePage>(`/api/datasets/images?limit=${PAGE}&offset=${items.length}`);
      setItems([...items, ...page.items]);
      setTotal(page.total);
      shown.current = items.length + page.items.length;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not load more images.");
    } finally {
      setLoadingMore(false);
    }
  }

  async function erase(image: StoredImage) {
    const ok = await confirm({
      title: "Delete this image?",
      message: `${shortName(image.name)} is permanently removed from the server. This cannot be undone.`,
      confirmLabel: "Delete image",
      danger: true,
    });
    if (!ok) return;
    setRemoving(image.name);
    setError("");
    try {
      await apiFetch(`/api/datasets/images/${encodeURIComponent(image.name)}`, { method: "DELETE" });
      setItems((current) => (current ? current.filter((i) => i.name !== image.name) : current));
      setTotal((t) => Math.max(0, t - 1));
      onChange();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not delete the image.");
    } finally {
      setRemoving(null);
    }
  }

  return (
    <Panel className="overflow-hidden" aria-labelledby="stored-images-title">
      <PanelHeader
        id="stored-images-title"
        title="Stored images"
        description={
          items && total > 0
            ? `${total.toLocaleString()} ${total === 1 ? "image" : "images"}, newest first. Only the name, size and time are listed.`
            : "Newest first. Only the name, size and time are listed."
        }
      />
      <PanelBody className="pt-4">
        {error && (
          <Notice tone="danger" role="alert" className="mb-4">
            {error}
          </Notice>
        )}
        {items === null ? (
          <div className="space-y-2" aria-busy="true" aria-label="Loading images">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton h-11 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState icon={<IconDatabase size={18} />} title="No images stored">
            Images you upload are listed here, and you can delete them one at a time.
          </EmptyState>
        ) : (
          <>
            <ul className="divide-y divide-line rounded border border-line">
              {items.map((image) => (
                <li key={image.name} className="flex items-center justify-between gap-4 px-3.5 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate font-mono text-[13px] text-ink">{shortName(image.name)}</p>
                    <p className="mt-0.5 text-xs text-ink-3">
                      {formatBytes(image.size_bytes)} ·{" "}
                      <time dateTime={image.uploaded_at}>{new Date(image.uploaded_at).toLocaleString()}</time>
                    </p>
                  </div>
                  <Button
                    variant="danger-quiet"
                    size="sm"
                    onClick={() => erase(image)}
                    loading={removing === image.name}
                    disabled={removing !== null}
                    aria-label={`Delete image ${shortName(image.name)}`}
                    className="shrink-0"
                  >
                    {removing !== image.name && <IconTrash size={14} />}
                    Delete
                  </Button>
                </li>
              ))}
            </ul>
            {items.length < total && (
              <div className="mt-4 flex justify-center">
                <Button variant="secondary" size="sm" onClick={showMore} loading={loadingMore}>
                  Show more ({(total - items.length).toLocaleString()} left)
                </Button>
              </div>
            )}
          </>
        )}
      </PanelBody>
    </Panel>
  );
}
