import Link from "next/link";
import StatusPage from "@/components/StatusPage";
import { buttonClass } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <StatusPage
      code="Error 404"
      title="Page not found"
      actions={
        <>
          <Link href="/" className={buttonClass("primary")}>
            Back to home
          </Link>
          <Link href="/dashboard" className={buttonClass("secondary")}>
            Open dashboard
          </Link>
        </>
      }
    >
      The page you were looking for does not exist or has moved.
    </StatusPage>
  );
}
