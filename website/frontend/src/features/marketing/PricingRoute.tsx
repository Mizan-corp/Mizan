import PricingPage from "@/features/billing/PricingPage";
import { openWithSession } from "@/lib/handoff";
import { useOwner } from "@app/lib/ownerSession";
import { useLocalePath } from "@app/seo/LocaleLink";
import { MarketingLayout } from "./MarketingLayout";

/** The pricing page, aware of a signed-in owner (#79): plan buttons open their panel. */
export default function PricingRoute() {
  const owner = useOwner();
  const sitePath = useLocalePath();
  return (
    <PricingPage
      layout={MarketingLayout}
      sitePath={sitePath}
      ownerPanel={owner ? (path) => openWithSession("owner", path, owner.token) : null}
    />
  );
}
