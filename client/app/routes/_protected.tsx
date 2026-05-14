import { Outlet, useNavigate } from "react-router";
import { useEffect } from "react";
import { useSession } from "~/lib/auth-client";

export default function ProtectedLayout() {
  const { data: session, isPending } = useSession();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isPending && !session) {
      navigate("/login", { replace: true });
    }
  }, [session, isPending, navigate]);

  if (isPending || !session) return null;

  return <Outlet />;
}
