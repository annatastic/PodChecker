import ResultsView from "./ResultsView";

const Results = ({ data, elapsed, onStartNew }: any) => {
  return (
    <ResultsView
      result={data}
      elapsed={elapsed}
      onStartNew={onStartNew}
    />
  );
}

export default Results;
