"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { expectSessionEnd } from "@/lib/session";
import { useConfirm } from "@/components/ConfirmProvider";
import SectionHeader from "@/components/dashboard/SectionHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import Button from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import PasswordInput from "@/components/ui/PasswordInput";
import FileDrop from "@/components/ui/FileDrop";
import Notice from "@/components/ui/Notice";
import EmptyState from "@/components/ui/EmptyState";
import { IconDatabase, IconTrash, IconUpload } from "@/components/ui/icons";

const UPLOAD_BATCH_MAX_FILES = 100;
const UPLOAD_BATCH_MAX_BYTES = 20 * 1024 * 1024;

interface Dataset {
  id: number;
  name: string;
  image_count: number;
  created_at: string;
}

export default function DataTab() {
  const confirm = useConfirm();
  const router = useRouter();
  const [datasets, setDatasets] = useState<Dataset[] | null>(null);
  const [selected, setSelected] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgIsError, setMsgIsError] = useState(false);
  const [erasing, setErasing] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [showDeletePassword, setShowDeletePassword] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const loadDatasets = useCallback(() => {
    apiFetch<Dataset[]>("/api/datasets")
      .then(setDatasets)
      .catch(() => setDatasets((d) => d ?? []));
  }, []);

  useEffect(() => {
    loadDatasets();
  }, [loadDatasets]);

  async function eraseData() {
    const ok = await confirm({
      title: "Delete all uploaded images?",
      message: "Every image you have uploaded is permanently removed from the server. This cannot be undone.",
      confirmLabel: "Delete images",
      danger: true,
    });
    if (!ok) return;
    setErasing(true);
    try {
      const res = await apiFetch<{ deleted_images: number }>("/api/datasets", { method: "DELETE" });
      setMsgIsError(false);
      setMsg(`Deleted ${res.deleted_images} images`);
      loadDatasets();
    } catch (err: unknown) {
      setMsgIsError(true);
      setMsg(err instanceof Error ? err.message : "Could not delete images.");
    } finally {
      setErasing(false);
    }
  }

  async function deleteAccount(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const ok = await confirm({
      title: "Delete your account?",
      message:
        "Your account, uploaded images and prediction history are permanently erased, and every session is ended. This cannot be undone.",
      confirmLabel: "Delete my account",
      danger: true,
    });
    if (!ok) return;
    setDeleting(true);
    setDeleteError("");
    try {
      await apiFetch("/api/auth/account", {
        method: "DELETE",
        body: JSON.stringify({ password: deletePassword }),
      });
      expectSessionEnd();
      localStorage.removeItem("hospital");
      router.push("/");
    } catch (err: unknown) {
      setDeleteError(err instanceof Error ? err.message : "Could not delete account.");
      setDeleting(false);
    }
  }

  async function handleUpload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const input = fileInput.current;
    if (!input?.files?.length) {
      setMsgIsError(true);
      setMsg("Please select image files first.");
      return;
    }

    setUploading(true);
    setMsg("");

    // The backend caps a request at 100 files / 25 MB; send big selections
    // as several requests instead of having the whole upload rejected.
    const batches: File[][] = [];
    let current: File[] = [];
    let currentBytes = 0;
    for (const f of Array.from(input.files)) {
      if (
        current.length > 0 &&
        (current.length >= UPLOAD_BATCH_MAX_FILES || currentBytes + f.size > UPLOAD_BATCH_MAX_BYTES)
      ) {
        batches.push(current);
        current = [];
        currentBytes = 0;
      }
      current.push(f);
      currentBytes += f.size;
    }
    if (current.length > 0) batches.push(current);

    let uploaded = 0;
    let totalImages = 0;
    try {
      for (const batch of batches) {
        const fd = new FormData();
        for (const f of batch) fd.append("files", f);
        const data = await apiFetch<{ uploaded: number; total_images: number }>("/api/datasets/upload", {
          method: "POST",
          body: fd,
        });
        uploaded += data.uploaded;
        totalImages = data.total_images;
      }
      setMsgIsError(false);
      setMsg(`Uploaded ${uploaded} images (${totalImages} total)`);
      input.value = "";
      setSelected([]);
    } catch (err: unknown) {
      setMsgIsError(true);
      setMsg(
        (uploaded > 0 ? `Uploaded ${uploaded} images before failing: ` : "") +
          (err instanceof Error ? err.message : "Upload failed. Is the backend running?"),
      );
    } finally {
      loadDatasets();
      setUploading(false);
    }
  }

  const totalImages = (datasets ?? []).reduce((s, d) => s + (d.image_count || 0), 0);

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Datasets"
        description="Wound images stored on this node. They are used for local training and never sent to other hospitals."
      />

      <Panel as="form" onSubmit={handleUpload} aria-labelledby="upload-title">
        <PanelHeader
          id="upload-title"
          title="Upload wound images"
          description="Large selections are sent in several smaller requests automatically."
        />
        <PanelBody className="space-y-4">
          <FileDrop
            ref={fileInput}
            id="dataset-files"
            accept="image/*"
            multiple
            title="Choose images"
            hint="JPEG or PNG, as many as you need"
            files={selected}
            onFiles={(f) => {
              setSelected(f);
              setMsg("");
            }}
            disabled={uploading}
          />
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-h-[1.25rem] text-[13px]" aria-live="polite">
              {msg && (
                <Notice tone={msgIsError ? "danger" : "success"} role={msgIsError ? "alert" : "status"}>
                  {msg}
                </Notice>
              )}
            </div>
            <Button type="submit" loading={uploading} disabled={selected.length === 0} className="sm:w-auto">
              {!uploading && <IconUpload size={16} />}
              {uploading ? "Uploading..." : selected.length > 1 ? `Upload ${selected.length} images` : "Upload"}
            </Button>
          </div>
        </PanelBody>
      </Panel>

      <Panel className="overflow-hidden">
        <PanelHeader
          title="Your datasets"
          description={
            datasets && datasets.length > 0
              ? `${datasets.length} ${datasets.length === 1 ? "dataset" : "datasets"}, ${totalImages.toLocaleString()} images in total.`
              : undefined
          }
        />
        <PanelBody className="pt-4">
          {datasets === null ? (
            <div className="space-y-2" aria-busy="true" aria-label="Loading datasets">
              {[0, 1, 2].map((i) => (
                <div key={i} className="skeleton h-12 w-full" />
              ))}
            </div>
          ) : datasets.length === 0 ? (
            <EmptyState icon={<IconDatabase size={18} />} title="No datasets yet">
              Upload some wound images above to create your first dataset.
            </EmptyState>
          ) : (
            <div className="relative -mx-5 overflow-x-auto sm:-mx-6">
              <table className="w-full min-w-[480px] text-sm">
                <thead>
                  <tr className="border-y border-line bg-canvas text-left">
                    <th scope="col" className="label-mono px-5 py-2.5 font-medium text-ink-3 sm:px-6">
                      Name
                    </th>
                    <th scope="col" className="label-mono px-4 py-2.5 text-right font-medium text-ink-3">
                      Images
                    </th>
                    <th scope="col" className="label-mono px-5 py-2.5 text-right font-medium text-ink-3 sm:px-6">
                      Created
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {datasets.map((d) => (
                    <tr key={d.id} className="border-b border-line last:border-b-0 hover:bg-canvas/60">
                      <td className="px-5 py-3 font-medium text-ink sm:px-6">{d.name}</td>
                      <td className="px-4 py-3 text-right text-ink-2 tabular">{d.image_count.toLocaleString()}</td>
                      <td className="px-5 py-3 text-right font-mono text-xs text-ink-3 tabular sm:px-6">
                        {d.created_at ? new Date(d.created_at).toLocaleDateString() : "Not recorded"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </PanelBody>
      </Panel>

      <Panel tone="danger" className="overflow-hidden" aria-labelledby="danger-title">
        <div className="border-b border-danger/20 bg-danger-soft/50 px-5 py-3 sm:px-6">
          <h2 id="danger-title" className="text-[13px] font-semibold text-danger-ink">
            Danger zone
          </h2>
        </div>
        <div className="divide-y divide-line">
          <div className="flex flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div className="max-w-xl">
              <h3 className="text-sm font-medium text-ink">Delete all uploaded images</h3>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
                Removes every image on this node. Your account and prediction history are kept.
              </p>
            </div>
            <Button
              variant="danger-quiet"
              onClick={eraseData}
              loading={erasing}
              disabled={!datasets || datasets.length === 0}
              className="shrink-0"
            >
              {!erasing && <IconTrash size={16} />}
              {erasing ? "Deleting..." : "Delete images"}
            </Button>
          </div>

          <form onSubmit={deleteAccount} className="grid gap-4 px-5 py-5 sm:px-6 lg:grid-cols-[1fr_minmax(0,22rem)] lg:gap-10">
            <div className="max-w-xl">
              <h3 className="text-sm font-medium text-ink">Delete account</h3>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
                Permanently removes your hospital account and every uploaded image. This cannot be undone.
              </p>
            </div>
            <div className="space-y-3">
              <Field label="Confirm with your password" htmlFor="delete-password" error={deleteError || undefined}>
                <PasswordInput
                  id="delete-password"
                  autoComplete="current-password"
                  required
                  maxLength={200}
                  value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)}
                  visible={showDeletePassword}
                  onToggle={() => setShowDeletePassword((s) => !s)}
                  aria-invalid={deleteError ? true : undefined}
                />
              </Field>
              <Button type="submit" variant="danger" loading={deleting} disabled={!deletePassword} className="w-full">
                {deleting ? "Deleting..." : "Delete account"}
              </Button>
            </div>
          </form>
        </div>
      </Panel>
    </div>
  );
}
