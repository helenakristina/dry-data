declare module "plotly.js-dist-min" {
  export * from "plotly.js";
}

declare module "react-plotly.js" {
  import { Component } from "react";
  import type Plotly from "plotly.js";

  interface PlotParams {
    data: Plotly.Data[];
    layout?: Partial<Plotly.Layout>;
    config?: Partial<Plotly.Config>;
    style?: React.CSSProperties;
    className?: string;
    useResizeHandler?: boolean;
    onInitialized?: (figure: Plotly.Figure) => void;
    onUpdate?: (figure: Plotly.Figure) => void;
  }

  export default class Plot extends Component<PlotParams> {}
}
