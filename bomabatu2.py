graph TD
    %% Define Styles
    classDef mongo fill:#4DB33D,stroke:#333,stroke-width:2px,color:white;
    classDef engine fill:#337ab7,stroke:#333,stroke-width:2px,color:white;
    classDef process fill:#f0f0f0,stroke:#333,stroke-width:1px,color:black;
    classDef ui fill:#f9f9f9,stroke:#333,stroke-width:2px;
    classDef userText fill:none,stroke:none,color:#555,font-style:italic;

    %% --- The "Platform KPI Framework" ---

    subgraph Platform_KPI_Framework [ ]
        direction LR

        %% Title
        Title[<b>Platform KPI Framework</b>]
        Title -.-.-> BaseEngine
        
        %% --- Source Agnostic Base Engine Section ---
        subgraph BaseEngine [Base Engine - Source Agnostic]
            direction LR
            ReadPrepare[Read Collections & Prepare for Collector]:::engine
            Collector[Collector: Collects Metrics]:::engine
            ReadPrepare -->|Prepares| Collector
        
            %% Annotations for the Base Engine logic
            Logic_Annotation[<div style='text-align:left;'>Reads config & settings<br/>Segregates data<br/>Identifies similar sources, apps, etc.</div>]:::userText
            Logic_Annotation -.-> ReadPrepare
        end

        %% --- Data Layer (Mongo) ---
        subgraph DataLayer [Mongo Collections]
            %% Left side collections
            ConfigCollection["Mongo Collection: config, settings,<br/>login details, etc."]:::mongo
            QueryCollection["Mongo Collection: onboarding,<br/>Queries, resources, inventory"]:::mongo

            %% Right side result collection
            ResultCollection["Mongo Collection (Results)"]:::mongo
        end

        %% --- Analysis & Output ---
        subgraph Analysis_Output [Analysis & Workflow]
            direction TB
            AnomalyDetector[Anomaly Detector]:::process
            Notification[Notification & Alerts]:::process
            AnomalyDetector -->|Feeds Data| Notification
            AnomalyDetector -.->|Stores Data?| MongoCollectionsOutput["Mongo Collections"]:::mongo
        end

        %% --- Connections & Flows ---
        UI_Users[UI - Users]:::ui
        Email[Email]:::process

        %% 1. Input/Onboarding Flow
        UI_Users -->|onboard| QueryCollection
        QueryCollection -->|Config Data| ReadPrepare
        ReadPrepare -.->|Reads (optional)| ConfigCollection

        %% 2. Data Gathering Flow
        Collector -->|Stores Aggregated Metrics| ResultCollection
        
        %% 3. Analysis/Anomaly Flow
        ResultCollection -->|Analyzes| AnomalyDetector

        %% 4. User Interaction/Output Flow
        UI_Users -->|subscribe| Notification
        Notification -->|sends| Email
    
    end

    %% --- The "How to Implement" Section ---

    subgraph Implementation_Advice [Implementation Proposal: Anomaly Detector]
        direction TB
        
        %% Question from sketch
        Question[<div style='border:2px solid red; padding:10px; font-weight:bold;'>“I have no idea how<br/>to implement this”</div>]
        
        %% Solution Box
        Solution[<div style='text-align:left;'><b>Proposed Implementation Stack:</b><br/><br/><b>1. Analysis (Choose one):</b><br/>• Simple: Statistics (e.g., Z-score, IQR)<br/>• Standard: FB Prophet (for time-series forecasting)<br/>• Advanced: ML (e.g., Isolation Forest, Autoencoders)<br/><br/><b>2. Storage:</b><br/>• Store anomaly events (timestamps, values, confidence) in Mongo.<br/><br/><b>3. Language:</b><br/>• Python is highly recommended (scikit-learn, prophet).<br/></div>]:::process

        Question --> Solution
    end
    
    %% Align the two main sections
    Analysis_Output -...- Implementation_Advice
    MongoCollectionsOutput -.->|Stored Data| Solution
