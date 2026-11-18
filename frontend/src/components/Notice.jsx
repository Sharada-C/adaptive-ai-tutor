// An inline message that replaces the browser alert() dialogs.

export default function Notice({ notice, onDismiss }) {
  if (!notice) {
    return null;
  }

  return (
    <div className={`notice notice-${notice.type}`} role="alert">
      <span>{notice.message}</span>

      <button
        type="button"
        className="notice-dismiss"
        aria-label="Dismiss message"
        onClick={onDismiss}
      >
        ×
      </button>
    </div>
  );
}
