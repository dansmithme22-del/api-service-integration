# C++ Add-On: Layout Annotator

## When to use this

Use this C++ Add-On **only** if the Python/JSON API cannot:

1. **Place 2D text elements** directly on Layout sheets.
2. **Read "elements visible on a Drawing"** — i.e. which model elements are
   shown through a specific placed Drawing on a Layout.

As of Archicad 29 the Python API does **not** expose `ACAPI_Element_Create`
for text/label elements on layouts.  The Add-On fills that gap.

---

## Architecture

```
Python  ──writes──►  output/SheetNotes.json
                           │
C++ Add-On  ◄──reads──────┘
    │
    ├─ Reads SheetNotes.json from a known path (configurable)
    ├─ Iterates layouts in the Layout Book
    ├─ For each layout, finds or creates a text element:
    │     ACAPI_Element_Create / ACAPI_Element_Change
    │     using API_TextType with multi-line content
    └─ Positions the text block at a defined anchor point
```

### Communication options

| Method | Pros | Cons |
|---|---|---|
| **JSON file on disk** | Simple; Python writes, C++ reads | Manual trigger needed |
| **ExecuteAddOnCommand** | Python triggers C++ via JSON API | Requires Add-On command registration |
| **Shared memory / socket** | Real-time | Over-engineering for this use-case |

**Recommended:** Register an Add-On command (`LayoutAnnotator::PlaceText`) so
Python can trigger placement via `ExecuteAddOnCommand`.

---

## Skeleton implementation

### 1. Register the Add-On command

```cpp
// In RegisterInterface():
ACAPI_AddOnAddOnCommunication_InstallAddOnCommandHandler(
    NewOwned<AnnotatorCommandHandler>()
);
```

### 2. Command handler

```cpp
class AnnotatorCommandHandler : public AddOnCommandHandler {
public:
    GS::String GetNamespace() const override { return "LayoutAnnotator"; }
    GS::String GetName()      const override { return "PlaceText"; }

    GS::Optional<GS::UniString> GetSchemaDefinitions() const override { return {}; }
    GS::Optional<GS::UniString> GetInputParametersSchema() const override {
        return R"({
            "type": "object",
            "properties": {
                "layoutGuid": {"type": "string"},
                "text":       {"type": "string"},
                "x":          {"type": "number"},
                "y":          {"type": "number"},
                "fontSize":   {"type": "number"}
            },
            "required": ["layoutGuid", "text"]
        })";
    }

    void OnResponseValidationFailed(const GS::ObjectState&) const override {}

    GS::ObjectState Execute(const GS::ObjectState& params,
                            const GS::ObjectState& /*context*/) const override
    {
        GS::UniString layoutGuid, text;
        double x = 0, y = 0, fontSize = 3.0;
        params.Get("layoutGuid", layoutGuid);
        params.Get("text", text);
        params.Get("x", x);
        params.Get("y", y);
        params.Get("fontSize", fontSize);

        // Switch to the target layout database
        API_DatabaseInfo dbInfo = {};
        // ... resolve layout GUID to database ...

        // Create text element
        API_Element     element = {};
        API_ElementMemo memo    = {};
        element.header.type = API_ObjectID; // or API_TextID if available
        // ... set position, content, font size ...

        GSErrCode err = ACAPI_Element_Create(&element, &memo);
        ACAPI_DisposeElemMemoHdls(&memo);

        GS::ObjectState result;
        result.Add("succeeded", err == NoError);
        result.Add("error", GS::UniString(err == NoError ? "" : "Element creation failed"));
        return result;
    }
};
```

### 3. Build with CMake (AC 29 DevKit)

```cmake
cmake_minimum_required(VERSION 3.16)
project(LayoutAnnotator)

set(AC_API_DEVKIT_DIR "path/to/AC29/APIDevKit")
# ... standard Archicad Add-On CMake setup ...
```

---

## Files to create

```
addons/layout_annotator_cpp/
├── CMakeLists.txt
├── Src/
│   ├── LayoutAnnotator.cpp      # Main entry, RegisterInterface, etc.
│   └── AnnotatorCommandHandler.h
├── RFIX/
│   └── LayoutAnnotator.grc      # Resource script
└── README.md                    # This file
```

Refer to Graphisoft's Add-On tutorial and the AC 29 C++ API Reference for
full `ACAPI_Element_Create` details with text elements.
