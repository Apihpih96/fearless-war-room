import { Component } from "react";

/**
 * React ErrorBoundary that wraps the draft board.
 * Catches any rendering error and shows a friendly reset button.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  reset = () => {
    this.setState({ hasError: false });
    // Clear the saved series so we start fresh
    try { localStorage.removeItem("fwr.series.v1"); } catch {}
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <h2>Something broke</h2>
          <p>The draft board encountered an error. You can start a new series to recover.</p>
          <button onClick={this.reset}>New series</button>
        </div>
      );
    }
    return this.props.children;
  }
}
